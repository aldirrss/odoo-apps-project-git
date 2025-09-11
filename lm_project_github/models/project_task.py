from odoo import fields, models, api, _
import requests
import json
from odoo.exceptions import UserError
from markupsafe import Markup


class ProjectTask(models.Model):
    _inherit = 'project.task'

    repository_id = fields.Many2one(comodel_name='project.github.repository', string="GitHub Repository",
                                    related='project_id.repository_id', store=True)
    auto_create_issues = fields.Boolean(string="Auto Create GitHub Issues", related='project_id.auto_create_issues')
    auto_update_issues = fields.Boolean(string="Auto Update GitHub Issues", related='project_id.auto_update_issues')
    github_issue_url = fields.Char(string="GitHub Issue URL", readonly=True)
    github_issue_number = fields.Integer(string="GitHub Issue Number", readonly=True)

    def _header_authentication(self):
        token = self.env.user.git_token
        if not token:
            raise UserError(_("GitHub token not found in user settings."))
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _get_existing_labels(self, repo_owner, repo_name):
        """Fetch existing labels from GitHub repo."""
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/labels"
        headers = self._header_authentication()
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return []
        return [l["name"] for l in res.json()]

    def _ensure_labels_exist(self, repo_owner, repo_name, labels):
        """Create labels in GitHub if they don't exist."""
        existing_labels = self._get_existing_labels(repo_owner, repo_name)
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/labels"
        headers = self._header_authentication()

        for label in labels:
            if label not in existing_labels:
                payload = {
                    "name": label,
                    "color": "a64d79",
                    "description": f"Auto-created from Odoo for tag '{label}'"
                }
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                if res.status_code not in (200, 201):
                    raise UserError(_("Failed to create label '%s': %s") %
                                    (label, res.json().get("message", "Unknown error")))

    def _prepare_github_issue_payload(self):
        """Prepare JSON payload for GitHub issue creation."""
        payload = {
            "title": self.name,
            "body": self.description or "No description provided.",
        }
        # Milestone
        if self.allow_milestones and self.milestone_id:
            payload["milestone"] = self.milestone_id.name

        # Labels (ensure exist before use)
        if self.tag_ids:
            labels = [tag.name for tag in self.tag_ids]
            self._ensure_labels_exist(self.repository_id.owner, self.repository_id.name, labels)
            payload["labels"] = labels

        # Assignees (map to git_username)
        if self.user_ids:
            assignees = [u.git_username for u in self.user_ids if u.git_username]
            if assignees:
                payload["assignees"] = assignees

        if self.stage_id and self.stage_id.name:
            closed_names = ["closed", "close", "done", "complete", "completed"]
            if self.stage_id.name.strip().lower() in closed_names:
                payload["state"] = "closed"
            else:
                payload["state"] = "open"

        return payload

    @api.model_create_multi
    def create(self, values):
        tasks = super().create(values)
        for task in tasks:
            if task.auto_create_issues and task.repository_id:
                task._action_create_github_issues()
        return tasks

    def write(self, values):
        res = super().write(values)
        for task in self:
            if task.auto_update_issues and task.repository_id and task.github_issue_url and not self.env.context.get(
                    "skip_github_update"):
                task._action_update_github_issue()
        return res

    def unlink(self):
        for task in self:
            if task.github_issue_url and task.repository_id:
                task._action_delete_github_issue()
        return super().unlink()

    def _action_create_github_issues(self):
        self.ensure_one()
        url = f"https://api.github.com/repos/{self.repository_id.owner}/{self.repository_id.name}/issues"
        headers = self._header_authentication()
        payload = self._prepare_github_issue_payload()

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 201:
                issue = response.json()
                self.with_context(skip_github_update=True).write({
                    "github_issue_url": issue.get("html_url"),
                    "github_issue_number": issue.get("number"),
                })
                message = _(
                    'Issues "%s" has been successfully created in repository %s.'
                ) % (self.name, self.repository_id.full_name)
                template_message = {
                    "message": message,
                    "action_link": issue.get("html_url"),
                    "action_text": _("View Issue")
                }
                self.message_post(body=Markup(self._get_log_message_template().format(**template_message)))
            else:
                msg = response.json().get("message", "Unknown error")
                raise UserError(_("Failed to create GitHub issue: %s") % msg)
        except requests.RequestException as e:
            raise UserError(_("Failed to connect to GitHub: %s") % str(e))

    def _action_update_github_issue(self):
        self.ensure_one()
        if not self.github_issue_url:
            raise UserError(_("No associated GitHub issue to update."))

        url = f"https://api.github.com/repos/{self.repository_id.owner}/{self.repository_id.name}/issues/{self.github_issue_number}"
        headers = self._header_authentication()
        payload = self._prepare_github_issue_payload()

        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                issue = response.json()
                self.message_post(body=_("GitHub issue %s updated") % issue.get("number"))
            else:
                msg = response.json().get("message", "Unknown error")
                raise UserError(_("Failed to update GitHub issue: %s") % msg)
        except requests.RequestException as e:
            raise UserError(_("Failed to connect to GitHub: %s") % str(e))

    def _action_delete_github_issue(self):
        self.ensure_one()
        if not self.github_issue_url:
            raise UserError(_("No associated GitHub issue to delete."))

        url = f"https://api.github.com/repos/{self.repository_id.owner}/{self.repository_id.name}/issues/{self.github_issue_number}"
        headers = self._header_authentication()

        try:
            response = requests.patch(url, headers=headers, json={"state": "closed"}, timeout=10)
            if response.status_code == 200:
                self.message_post(
                    body=_("GitHub issue closed: <a href='%s'>%s</a>") % (self.github_issue_url, self.github_issue_url))
                self.github_issue_url = False
                self.github_issue_number = False
            else:
                msg = response.json().get("message", "Unknown error")
                raise UserError(_("Failed to close GitHub issue: %s") % msg)
        except requests.RequestException as e:
            raise UserError(_("Failed to connect to GitHub: %s") % str(e))

    def action_create_github_issue(self):
        pass

    def action_update_github_issue(self):
        pass

    def _get_log_message_template(self):
        """Return HTML template for log message."""
        return """
            <div style="background-color: #DDF4E7; padding: 12px; border-radius: 8px; border-left: 4px solid #96CEB4">
                <p style="color: #495057;">{message}</p>
                <div style="text-align: right;">
                    <a href="{action_link}" 
                       style="color: #5D4765; text-decoration: underline; font-size: 12px;">
                        {action_text}
                    </a>
                </div>
            </div>
        """
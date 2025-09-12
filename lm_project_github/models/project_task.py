from odoo import fields, models, api, _
import requests
import json
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
import logging


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Constants
    _github_api_base_url = "https://api.github.com"
    _request_timeout = 10
    _closed_stage_names = ["closed", "close", "done", "complete", "completed"]
    _default_label_color = "a64d79"

    # GitHub Integration Fields
    repository_id = fields.Many2one(
        comodel_name='project.github.repository',
        string="GitHub Repository",
        related='project_id.repository_id',
        store=True
    )
    auto_create_issues = fields.Boolean(
        string="Auto Create GitHub Issues",
        related='project_id.auto_create_issues'
    )
    auto_update_issues = fields.Boolean(
        string="Auto Update GitHub Issues",
        related='project_id.auto_update_issues'
    )
    github_issue_url = fields.Char(
        string="GitHub Issue URL",
        readonly=True
    )
    github_issue_number = fields.Integer(
        string="GitHub Issue Number",
        readonly=True
    )
    branch_id = fields.Many2one(
        comodel_name='project.github.branch',
        string="GitHub Branch",
        domain="[('repository_id', '=', repository_id)]"
    )
    pull_request_url = fields.Char(
        string="Pull Request URL",
        readonly=True
    )
    pull_request_number = fields.Integer(
        string="Pull Request Number",
        readonly=True
    )
    pull_request_merged = fields.Boolean(
        string="Pull Request Merged",
        readonly=True,
        default=True
    )

    # ========================================
    # AUTHENTICATION & HTTP HELPERS
    # ========================================

    def _get_auth_headers(self):
        """Get authentication headers for GitHub API requests."""
        token = self.env.user.git_token
        if not token:
            raise UserError(_("GitHub token not found in user settings."))
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _make_github_request(self, method, endpoint, payload=None, expected_status=(200,)):
        """Make authenticated request to GitHub API with error handling."""
        if not isinstance(expected_status, (list, tuple)):
            expected_status = (expected_status,)

        url = f"{self._github_api_base_url}{endpoint}"
        headers = self._get_auth_headers()

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=self._request_timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=payload, timeout=self._request_timeout)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=payload, timeout=self._request_timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=self._request_timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code not in expected_status:
                error_msg = response.json().get("message", "Unknown error")
                raise UserError(_("GitHub API error: %s") % error_msg)

            return response.json() if response.content else {}

        except requests.RequestException as e:
            raise UserError(_("Failed to connect to GitHub: %s") % str(e))

    # ========================================
    # GITHUB RESOURCE MANAGEMENT
    # ========================================

    def _get_existing_labels(self):
        """Fetch existing labels from GitHub repository."""
        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/labels"
        try:
            labels_data = self._make_github_request('GET', endpoint)
            return [label["name"] for label in labels_data]
        except UserError:
            return []

    def _ensure_labels_exist(self, labels):
        """Create labels in GitHub if they don't exist."""
        if not labels:
            return

        existing_labels = self._get_existing_labels()
        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/labels"

        for label in labels:
            if label not in existing_labels:
                payload = {
                    "name": label,
                    "color": self._default_label_color,
                    "description": f"Auto-created from Odoo for tag '{label}'"
                }
                self._make_github_request('POST', endpoint, payload, (200, 201))

    def _get_milestone_number(self, milestone_title, due_on=None):
        """Get or create milestone and return its number."""
        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/milestones"
        milestones = self._make_github_request('GET', endpoint)

        # Check if milestone already exists
        for milestone in milestones:
            if milestone["title"] == milestone_title:
                return milestone["number"]

        # Create milestone if not found
        payload = {
            "title": milestone_title,
            "state": "open",
            "description": f"Auto-created from Odoo for milestone '{milestone_title}'"
        }
        if due_on:
            payload["due_on"] = due_on

        milestone_data = self._make_github_request('POST', endpoint, payload, (200, 201))
        return milestone_data.get("number")

    # ========================================
    # PAYLOAD PREPARATION
    # ========================================

    def _prepare_github_issue_payload(self):
        """Prepare JSON payload for GitHub issue creation/update."""
        payload = {
            "title": self.name,
            "body": self.description or "No description provided.",
        }

        # Add milestone
        if hasattr(self, 'allow_milestones') and self.allow_milestones and self.milestone_id:
            milestone_number = self._get_milestone_number(
                self.milestone_id.name,
                self.milestone_id.deadline
            )
            if milestone_number:
                payload["milestone"] = milestone_number

        # Add labels
        if self.tag_ids:
            labels = [tag.name.strip().lower() for tag in self.tag_ids]
            self._ensure_labels_exist(labels)
            payload["labels"] = labels

        # Add assignees
        if self.user_ids:
            assignees = [u.git_username for u in self.user_ids if u.git_username]
            if assignees:
                payload["assignees"] = assignees

        # Set state based on stage
        if self.stage_id and self.stage_id.name:
            stage_name = self.stage_id.name.strip().lower()
            payload["state"] = "closed" if stage_name in self._closed_stage_names else "open"

        return payload

    def _prepare_branch_payload(self, branch_name, base_branch="main"):
        """Prepare payload for branch creation."""
        # Get the SHA of the base branch
        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/git/ref/heads/{base_branch}"
        ref_data = self._make_github_request('GET', endpoint)

        return {
            "ref": f"refs/heads/{branch_name}",
            "sha": ref_data["object"]["sha"]
        }

    def _prepare_pull_request_payload(self, title, body, head_branch, base_branch="main"):
        """Prepare payload for pull request creation."""
        return {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": False
        }

    # ========================================
    # ODOO LIFECYCLE METHODS
    # ========================================

    @api.model_create_multi
    def create(self, values):
        """Override create to auto-create GitHub issues."""
        tasks = super().create(values)
        for task in tasks:
            if task.auto_create_issues and task.repository_id:
                try:
                    task._create_github_issue()
                except Exception as e:
                    raise UserError(_("Failed to auto-create GitHub issue for task %s: %s") % (task.name, str(e)))
        return tasks

    def write(self, values):
        """Override write to auto-update GitHub issues."""
        res = super().write(values)
        for task in self:
            if (task.auto_update_issues and task.repository_id and
                    task.github_issue_url and not self.env.context.get("skip_github_update")):
                try:
                    task._update_github_issue()
                except Exception as e:
                    raise UserError(_("Failed to auto-update GitHub issue for task %s: %s") % (task.name, str(e)))
        return res

    def unlink(self):
        """Override unlink to close GitHub issues."""
        for task in self:
            if task.github_issue_url and task.repository_id:
                try:
                    task._close_github_issue()
                except Exception as e:
                    raise UserError(_("Failed to close GitHub issue for task %s: %s") % (task.name, str(e)))
        return super().unlink()

    # ========================================
    # GITHUB ISSUE OPERATIONS
    # ========================================

    def _create_github_issue(self):
        """Create GitHub issue from task."""
        self.ensure_one()
        self._validate_github_setup()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/issues"
        payload = self._prepare_github_issue_payload()

        issue_data = self._make_github_request('POST', endpoint, payload, 201)

        self.with_context(skip_github_update=True).write({
            "github_issue_url": issue_data.get("html_url"),
            "github_issue_number": issue_data.get("number"),
        })

        self._post_success_message(
            _('GitHub issue "%s" has been successfully created in repository %s.') %
            (self.name, self.repository_id.full_name),
            issue_data.get("html_url"),
            _("View Issue")
        )

    def _update_github_issue(self):
        """Update existing GitHub issue."""
        self.ensure_one()
        self._validate_github_issue_exists()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/issues/{self.github_issue_number}"
        payload = self._prepare_github_issue_payload()

        issue_data = self._make_github_request('PATCH', endpoint, payload)

        self.message_post(
            body=_("GitHub issue #%s updated successfully") % issue_data.get("number")
        )

    def _close_github_issue(self):
        """Close GitHub issue."""
        self.ensure_one()
        self._validate_github_issue_exists()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/issues/{self.github_issue_number}"
        payload = {"state": "closed"}

        self._make_github_request('PATCH', endpoint, payload)

        self.message_post(
            body=_("GitHub issue closed: <a href='%s'>%s</a>") %
                 (self.github_issue_url, self.github_issue_url)
        )

        # self.write({
        #     "github_issue_url": False,
        #     "github_issue_number": False
        # })

    # ========================================
    # GITHUB BRANCH OPERATIONS
    # ========================================

    def _create_github_branch(self, branch_name, base_branch="main"):
        """Create GitHub branch."""
        self.ensure_one()
        self._validate_github_setup()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/git/refs"
        payload = self._prepare_branch_payload(branch_name, base_branch)

        branch_data = self._make_github_request('POST', endpoint, payload, 201)

        # Update or create branch record
        branch = self.env['project.github.branch'].search([
            ('name', '=', branch_name),
            ('repository_id', '=', self.repository_id.id),
            ('project_id', '=', self.project_id.id)
        ])

        if not branch:
            branch = self.env['project.github.branch'].create({
                'name': branch_name,
                'repository_id': self.repository_id.id,
                'project_id': self.project_id.id,
            })

        self.branch_id = branch.id

        self._post_success_message(
            _('GitHub branch "%s" has been successfully created.') % branch_name,
            f"https://github.com/{self.repository_id.owner}/{self.repository_id.name}/tree/{branch_name}",
            _("View Branch")
        )

    def _delete_github_branch(self, branch_name):
        """Delete GitHub branch."""
        self.ensure_one()
        self._validate_github_setup()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/git/refs/heads/{branch_name}"

        self._make_github_request('DELETE', endpoint, expected_status=(204, 404))

        # Remove branch record
        if self.branch_id and self.branch_id.name == branch_name:
            self.branch_id.unlink()
            self.branch_id = False

        self.message_post(
            body=_("GitHub branch '%s' has been deleted.") % branch_name
        )

    # ========================================
    # GITHUB PULL REQUEST OPERATIONS
    # ========================================

    def _create_pull_request(self, title, body, head_branch, base_branch="main"):
        """Create GitHub pull request."""
        self.ensure_one()
        self._validate_github_setup()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/pulls"
        payload = self._prepare_pull_request_payload(title, body, head_branch, base_branch)

        pr_data = self._make_github_request('POST', endpoint, payload, 201)

        self.write({
            "pull_request_url": pr_data.get("html_url"),
            "pull_request_number": pr_data.get("number"),
            "pull_request_merged": False,
        })

        self._post_success_message(
            _('Pull request "%s" has been successfully created.') % title,
            pr_data.get("html_url"),
            _("View Pull Request")
        )

    def _merge_pull_request(self, merge_method="merge"):
        """Merge GitHub pull request."""
        self.ensure_one()
        self._validate_pull_request_exists()

        endpoint = f"/repos/{self.repository_id.owner}/{self.repository_id.name}/pulls/{self.pull_request_number}/merge"
        payload = {
            "commit_title": f"Merge pull request #{self.pull_request_number}",
            "merge_method": merge_method
        }

        merge_data = self._make_github_request('PUT', endpoint, payload)

        if merge_data:
            self.write({
                "pull_request_url": False,
                "pull_request_number": False,
                "pull_request_merged": True,
            })

        self.message_post(
            body=_("Pull request #%s merged successfully: <a href='%s'>%s</a>") %
                 (self.pull_request_number, self.pull_request_url, self.pull_request_url)
        )

    # ========================================
    # VALIDATION HELPERS
    # ========================================

    def _validate_github_setup(self):
        """Validate GitHub setup before operations."""
        if not self.repository_id:
            raise ValidationError(_("No GitHub repository configured for this task."))
        if not self.env.user.git_token:
            raise ValidationError(_("GitHub token not found in user settings."))

    def _validate_github_issue_exists(self):
        """Validate that GitHub issue exists."""
        if not self.github_issue_url or not self.github_issue_number:
            raise ValidationError(_("No associated GitHub issue found."))

    def _validate_pull_request_exists(self):
        """Validate that pull request exists."""
        if not self.pull_request_url or not self.pull_request_number:
            raise ValidationError(_("No associated pull request found."))

    # ========================================
    # UI HELPERS
    # ========================================

    def _post_success_message(self, message, action_link, action_text):
        """Post success message with action link."""
        template_data = {
            "message": message,
            "action_link": action_link,
            "action_text": action_text
        }
        self.message_post(
            body=Markup(self._get_log_message_template().format(**template_data))
        )

    def _get_log_message_template(self):
        """Return HTML template for log messages."""
        return """
            <div style="background-color: #DDF4E7; padding: 12px; border-radius: 8px; border-left: 4px solid #96CEB4">
                <p style="color: #495057;">{message}</p>
                <div style="text-align: right;">
                    <a href="{action_link}" 
                       style="color: #5D4765; text-decoration: underline; font-size: 12px;" target="_blank">
                        {action_text}
                    </a>
                </div>
            </div>
        """

    # ========================================
    # PUBLIC ACTION METHODS
    # ========================================

    def action_open_github_issue(self):
        """Open GitHub issue in new tab."""
        self.ensure_one()
        self._validate_github_issue_exists()
        return {
            "type": "ir.actions.act_url",
            "url": self.github_issue_url,
            "target": "new",
        }

    def action_create_github_issue(self):
        """Manual action to create GitHub issue."""
        self.ensure_one()
        if self.github_issue_url:
            raise UserError(_("GitHub issue already exists for this task."))
        self._create_github_issue()

    def action_update_github_issue(self):
        """Manual action to update GitHub issue."""
        self.ensure_one()
        self._update_github_issue()

    def action_create_branch(self):
        """Manual action to create GitHub branch."""
        self.ensure_one()
        branch_name = f"task-{self.id}-{self.name}".lower().replace(" ", "-")[:50]
        self._create_github_branch(branch_name)

    def action_delete_branch(self):
        """Manual action to delete GitHub branch."""
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("No branch associated with this task."))
        self._delete_github_branch(self.branch_id.name)

    def action_create_pull_request(self):
        """Manual action to create pull request."""
        self.ensure_one()
        if not self.branch_id:
            raise UserError(_("No branch associated with this task. Create a branch first."))

        title = f"[Task #{self.id}] {self.name}"
        body = f"Resolves task: {self.name}\n\n{self.description or 'No description provided.'}"

        self._create_pull_request(title, body, self.branch_id.name)

    def action_merge_pull_request(self):
        """Manual action to merge pull request."""
        self.ensure_one()
        self._merge_pull_request()

    def action_open_pull_request(self):
        """Open pull request in new tab."""
        self.ensure_one()
        self._validate_pull_request_exists()
        return {
            "type": "ir.actions.act_url",
            "url": self.pull_request_url,
            "target": "new",
        }
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import requests
from markupsafe import Markup
from datetime import datetime


class Project(models.Model):
    _inherit = "project.project"

    enable_github = fields.Boolean(string="GitHub Connection", default=False)
    repository_id = fields.Many2one(
        comodel_name="project.github.repository",
        string="GitHub Repository", ondelete="set null"
    )
    is_connected_github = fields.Boolean(string="Connected", default=False)
    github_url = fields.Char(string="GitHub URL", readonly=True)

    # Commit management
    commit_prefix = fields.Char(string="Commit Prefix", help="Prefix to identify commits related to this project.")
    commit_ids = fields.One2many(
        comodel_name="project.github.commit",
        inverse_name="project_id",
        string="Commits",
        help="Commits associated with this project."
    )
    commit_count = fields.Integer(
        string="Commit Count",
        compute="_compute_commit_count",
        help="Number of commits associated with this project."
    )

    # Branch management
    default_branch_id = fields.Many2one(
        comodel_name="project.github.branch",
        string="Default Branch",
        related="repository_id.default_branch_id",
        readonly=False,
        help="The default branch of the connected GitHub repository."
    )
    branch_ids = fields.Many2many(
        comodel_name="project.github.branch",
        string="Branches",
        help="Branches of the connected GitHub repository."
    )

    # Webhook management
    project_webhook_id = fields.Many2one(
        comodel_name="project.github.webhook",
        string="Webhook Configuration", help="Webhook configured for this project."
    )

    # Issues management
    auto_create_issues = fields.Boolean(string="Auto-create Issues on Tasks Creation", default=False)
    auto_update_issues = fields.Boolean(string="Auto-update Issues on Tasks Update", default=False)
    automation_workflow = fields.Boolean(string="Enable Automation Workflow", default=False)

    @api.onchange('automation_workflow')
    def _onchange_automation_workflow(self):
        if not self.automation_workflow:
            self.auto_create_issues = False
            self.auto_update_issues = False
        else:
            self.auto_create_issues = True
            self.auto_update_issues = True

    @api.constrains('auto_create_issues')
    def _check_auto_create_issues(self):
        for project in self:
            if not project.auto_create_issues and project.automation_workflow and project.enable_github:
                raise UserError(_("To enable 'Automation Workflow', 'Auto-create Issues on Tasks Creation' must be enabled."))

    def _header_authentication(self):
        token = self.env.user.git_token
        if not token:
            raise UserError(_("GitHub token not found in user settings. Please set it to proceed."))
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def action_connect_repository(self):
        action = self.env.ref('lm_project_github.action_project_github_connect_repository').read()[0]
        action['context'] = {'default_project_id': self.id, 'default_github_username': self.env.user.git_username}
        return action

    def action_view_repository(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'GitHub Repository',
            'res_model': 'project.github.repository',
            'view_mode': 'form',
            'res_id': self.repository_id.id,
            'target': 'new',
        }

    def action_disconnect_repository(self):
        self.ensure_one()
        if not self.repository_id:
            raise UserError(_("No repository linked to revoke."))
        repo_name = self.repository_id.full_name
        headers = self._header_authentication()
        base_url = f'https://api.github.com/repos/{repo_name}'

        try:
            response = requests.delete(f'{base_url}/hooks', headers=headers)
            if response.status_code not in [204, 404]:
                raise UserError(_("Failed to delete webhooks on GitHub."))
            self.repository_id.unlink()
            self.enable_github = False
            self.is_connected_github = False
            self.github_url = False
            self.message_post(body=_("Disconnected from GitHub repository %s." % repo_name))
        except requests.RequestException as e:
            raise UserError(_("Error during disconnection: %s" % str(e)))

    def action_sync_branches(self):
        self.ensure_one()
        if not self.is_connected_github:
            raise UserError(_("Repository is not connected. Please connect the repository first."))

        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        try:
            response = requests.get(
                f'{base_url}/repos/{self.repository_id.full_name}/branches',
                headers=self._header_authentication(),
                timeout=10
            )
            if response.status_code == 200:
                branches = response.json()
                existing_branch_names = self.branch_ids.mapped('name')
                new_branches = []
                for branch in branches:
                    if branch['name'] not in existing_branch_names:
                        new_branch = self.env['project.github.branch'].create({
                            'name': branch['name'],
                            'project_id': self.id,
                            'repository_id': self.repository_id.id,
                        })
                        new_branches.append(new_branch)
                if new_branches:
                    self.branch_ids = [(4, b.id) for b in new_branches]
                    self.message_post(
                        body=_("Synchronized branches successfully. Added %d new branches." % len(new_branches)))
                else:
                    raise UserError(_("No new branches found to synchronize."))
            else:
                raise UserError(_("Failed to fetch branches from GitHub. Status Code: %s" % response.status_code))
        except requests.RequestException as e:
            raise UserError(_("An error occurred while connecting to GitHub: %s" % str(e)))

    def action_sync_commits(self):
        self.ensure_one()
        if not self.is_connected_github:
            raise UserError(_("Repository is not connected. Please connect the repository first."))

        base_url = self.env.company.github_instance_url or 'https://api.github.com'
        headers = self._header_authentication()

        try:
            branches_res = requests.get(
                f'{base_url}/repos/{self.repository_id.full_name}/branches',
                headers=headers, timeout=10
            )
            if branches_res.status_code != 200:
                raise UserError(_("Failed to fetch branches. %s" % branches_res.text))
            branches = branches_res.json()

            new_commits = []
            for branch in branches:
                branch_name = branch['name']
                branch_rec = self.env['project.github.branch'].search([
                    ('name', '=', branch_name),
                    ('project_id', '=', self.id)
                ], limit=1)
                if not branch_rec:
                    branch_rec = self.env['project.github.branch'].create({
                        'name': branch_name,
                        'project_id': self.id,
                    })

                commits_res = requests.get(
                    f'{base_url}/repos/{self.repository_id.full_name}/commits?sha={branch_name}',
                    headers=headers, timeout=10
                )
                if commits_res.status_code != 200:
                    continue

                for commit in commits_res.json():
                    commit_data = commit['commit']
                    commit_hash = commit['sha']

                    commit_rec = self.env['project.github.commit'].search([
                        ('commit_hash', '=', commit_hash),
                        ('project_id', '=', self.id),
                    ], limit=1)

                    if not commit_rec:
                        commit_date = datetime.strptime(
                            commit_data['author']['date'], "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=None)

                        commit_rec = self.env['project.github.commit'].create({
                            'task_id': False,
                            'project_id': self.id,
                            'commit_hash': commit_hash,
                            'author_name': commit_data['author']['name'],
                            'author_email': commit_data['author']['email'],
                            'commiter_name': commit_data['committer']['name'],
                            'commiter_email': commit_data['committer']['email'],
                            'name': commit_data['message'],
                            'commit_url': commit['html_url'],
                            'date': commit_date,
                            'branch_ids': [(6, 0, [branch_rec.id])],
                        })
                        new_commits.append(commit_rec)
                    else:
                        if branch_rec.id not in commit_rec.branch_ids.ids:
                            commit_rec.branch_ids = [(4, branch_rec.id)]

            if new_commits:
                self.commit_ids = [(4, c.id) for c in new_commits]
                self.message_post(body=_("Synchronized %d new commits across all branches." % len(new_commits)))
            else:
                raise UserError(_("No new commits found to synchronize."))

        except requests.RequestException as e:
            raise UserError(_("GitHub connection error: %s" % str(e)))

    def action_view_commits(self):
        self.ensure_one()
        return {
            'name': _('Commits'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.commit',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'duplicate': False},
            'target': 'current',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        There are no commits for this project.
                        </p>
                    '''),
        }

    @api.depends('commit_ids')
    def _compute_commit_count(self):
        for project in self:
            project.commit_count = len(project.commit_ids)

    def action_create_webhook(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'GitHub Webhook Configuration',
            'res_model': 'project.github.create.webhook',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id},
        }

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

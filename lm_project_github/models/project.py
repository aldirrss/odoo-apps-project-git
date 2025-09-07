from odoo import fields, models, api, _
from odoo.exceptions import UserError
import requests
from markupsafe import Markup


class Project(models.Model):
    _inherit = "project.project"

    enable_github = fields.Boolean(string="GitHub Connection", default=False)
    repository_id = fields.Many2one(
        comodel_name="project.github.repository",
        string="GitHub Repository", ondelete="set null"
    )
    is_connected_github = fields.Boolean(string="Connected", default=False)
    github_url = fields.Char(string="GitHub URL", readonly=True)

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
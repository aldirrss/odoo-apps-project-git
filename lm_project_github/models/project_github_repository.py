import requests
from markupsafe import Markup
from odoo import fields, models, api, _
from odoo.api import ValuesType, Self
from odoo.exceptions import UserError


class ProjectGithubRepository(models.Model):
    _name = "project.github.repository"
    _description = "Project Github Repository"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Display Name", required=True, tracking=True)
    description = fields.Text(string="Description")
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        ondelete="cascade",
        readonly=True,
    )
    commit_code = fields.Char(string="Commit Code", size=5, tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    connected = fields.Boolean(string="Connected", default=False)

    # GitHub specific fields
    repository = fields.Char(string="Repository Name", help="Format: owner/repo")
    url = fields.Char(string="URL")

    def copy(self, default=None):
        raise UserError(_("Duplication of GitHub Repository records is not allowed."))

    def _header_authentication(self):
        token = self.env.user.git_token
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def action_connect_repository(self):
        self.ensure_one()
        if not self.repository:
            raise UserError(_("Repository name is not set."))

        token = self.env.user.git_token
        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        if not token:
            raise UserError(_("GitHub token is not set for the user."))

        try:
            response = requests.get(
                f'{base_url}/repos/{self.repository}',
                headers=self._header_authentication(),
                timeout=10
            )
            if response.status_code == 200:
                repo_data = response.json()
                self.write({
                    'description': repo_data.get('description', ''),
                    'url': repo_data.get('html_url', ''),
                    'connected': True,
                })
                message = {
                    'message': _("Connected to GitHub repository successfully."),
                    'action_link': repo_data.get('html_url', ''),
                    'action_text': _("View Repository"),
                }
                self.message_post(body=Markup(self._get_log_message_template()).format(**message))
            else:
                self.write({'connected': False})
                raise UserError(_("Failed to connect to the repository. Please check the repository name and your credentials."))
        except requests.RequestException as e:
            self.write({'connected': False})
            raise UserError(_("An error occurred while connecting to GitHub: %s") % str(e))

    def _get_log_message_template(self):
        """Return HTML template for log message."""
        return """
            <div style="background-color: #DDF4E7; padding: 15px; border-radius: 8px; border-left: 4px solid #67C090; margin: 8px 0;">
                <p style="color: #495057;"><i class="fa fa-info-circle" style="margin-right: 8px;"></i>{message}</p>
                <div style="margin-top: 8px;">
                    <a href="{action_link}" 
                       style="display: inline-block; padding: 8px 8px; background-color: #5D4765; color: white; text-decoration: none; border-radius: 4px; font-size: 12px;">
                        {action_text}
                    </a>
                </div>
            </div>
        """
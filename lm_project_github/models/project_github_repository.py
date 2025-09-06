import requests
from markupsafe import Markup
from odoo import fields, models, api, _
import base64
from odoo.exceptions import UserError


class ProjectGithubRepository(models.Model):
    _name = "project.github.repository"
    _description = "Project Github Repository"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    _sql_constraints = [
        ('owner_name_uniq', 'unique(owner, name)', 'The repository name must be unique per owner!'),
    ]

    name = fields.Char(string="Repository", required=True, tracking=True)
    description = fields.Text(string="Description")
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        ondelete="cascade",
        readonly=True,
    )
    commit_prefix = fields.Char(string="Commit Code", size=5, tracking=True)
    images = fields.Binary(string="Image", attachment=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    is_connected = fields.Boolean(string="Connected", default=False)

    owner = fields.Char(string="Owner", required=True, tracking=True)
    # load image from github api
    avatar_url = fields.Char(string="Avatar URL", readonly=True)
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
        if not self.name:
            raise UserError(_("Repository name is not set."))

        token = self.env.user.git_token
        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        if not token:
            raise UserError(_("GitHub token is not set for the user."))

        try:
            response = requests.get(
                f'{base_url}/repos/{self.name}',
                headers=self._header_authentication(),
                timeout=10
            )
            if response.status_code == 200:
                repo_data = response.json()
                avatar_url = repo_data.get('owner', {}).get('avatar_url', '')
                image = base64.b64encode(requests.get(avatar_url.strip()).content).replace(b"\n", b"")
                self.write({
                    'description': repo_data.get('description', ''),
                    'url': repo_data.get('html_url', ''),
                    'avatar_url': repo_data.get('owner', {}).get('avatar_url', ''),
                    'is_connected': True,
                })
                message = {
                    'message': _("Connected to GitHub repository successfully."),
                    'action_link': repo_data.get('html_url', ''),
                    'action_text': _("View"),
                }
                self.message_post(body=Markup(self._get_log_message_template()).format(**message))
            else:
                self.write({'is_connected': False})
                raise UserError(_("Failed to connect to the repository. Please check the repository name and your credentials."))
        except requests.RequestException as e:
            self.write({'is_connected': False})
            raise UserError(_("An error occurred while connecting to GitHub: %s") % str(e))

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

    def action_create_webhook(self):
        pass

    def action_delete_webhook(self):
        pass

    def action_create_branch(self):
        pass

    def action_sync_branch(self):
        pass

    def action_delete_branch(self):
        pass
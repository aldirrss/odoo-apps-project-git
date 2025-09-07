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

    def _header_authentication(self):
        token = self.env.user.git_token
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def action_connect_repository(self):
        action = self.env.ref('lm_project_github.action_project_github_connect_repository').read()[0]
        action['context'] = {'default_project_id': self.id, 'default_github_username': self.env.user.git_username}
        return action

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
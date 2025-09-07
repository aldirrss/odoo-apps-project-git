from odoo import fields, models, api


class Project(models.Model):
    _inherit = "project.project"

    enable_github = fields.Boolean(string="GitHub Connection", default=False)
    github_repository = fields.Char(
        string="GitHub Repository",
        help="GitHub repository in the format 'owner/repo'"
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
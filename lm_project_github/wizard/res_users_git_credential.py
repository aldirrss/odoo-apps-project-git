from odoo import fields, models, api
import hashlib


class ResUsersGitCredential(models.TransientModel):
    _name = 'res.users.git.credential'
    _description = 'Git Credentials Wizard'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    git_username = fields.Char(
        string='Git Username',
        required=True,
        help='GitLab Username for authentication',
    )
    git_token = fields.Char(
        string='Git Token',
        required=True,
        help='Personal Access Token for Git integration',
    )
    git_provider = fields.Selection(
        [('gitlab', 'GitLab'), ('github', 'GitHub')],
        string='Provider', default='gitlab', required=True
    )

    def action_confirm(self):
        for record in self:
            record.user_id.git_username = record.git_username
            record.user_id.git_token = record.git_token
            record.user_id.is_connected = False
        return {'type': 'ir.actions.act_window_close'}
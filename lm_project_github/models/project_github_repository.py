import requests
from datetime import datetime
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
    date_connected = fields.Datetime(string="Connected On", readonly=True)
    commit_prefix = fields.Char(string="Commit Prefix", size=5, tracking=True)
    images = fields.Binary(string="Image", attachment=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    is_connected = fields.Boolean(string="Connected", default=False)
    owner = fields.Char(string="Owner", required=True, tracking=True)
    github_id = fields.Char(string="Github Id", readonly=True)
    avatar_url = fields.Char(string="Avatar URL", readonly=True)
    url = fields.Char(string="URL")

    # Webhook Configuration Fields
    webhook_id = fields.Integer(
        string='Webhook ID',
        help='ID of the webhook in GitLab',
    )
    webhook_url = fields.Char(
        string='Webhook URL',
        help='URL of the webhook in GitLab',
    )
    webhook_name = fields.Char(
        string='Webhook',
        help='Name of the webhook in GitLab',
    )

    # Branch Configuration Fields
    branch_ids = fields.One2many(
        comodel_name='project.github.branch',
        inverse_name='repository_id',
        string='Branches',
        help='Branches associated with this repository',
    )
    branch_count = fields.Integer(
        string='Branch Count',
        compute='_compute_branch_count',
        store=True,
    )

    def _compute_display_name(self):
        for record in self:
            if record.owner and record.name:
                record.display_name = f"{record.owner}/{record.name}"
            else:
                record.display_name = record.name or "New"

    def copy(self, default=None):
        raise UserError(_("Duplication of GitHub Repository records is not allowed."))

    def _header_authentication(self):
        token = self.env.user.git_token
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        }

    def action_create_repository(self):
        return {
            'name': _('Create GitHub Repository'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.create.repository',
            'view_mode': 'form',
            'target': 'new',
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
                f'{base_url}/repos/{self.owner}/{self.name}',
                headers=self._header_authentication(),
                timeout=10
            )
            if response.status_code == 200:
                repo_data = response.json()
                avatar_url = repo_data.get('owner', {}).get('avatar_url', '')
                image = base64.b64encode(requests.get(avatar_url.strip()).content).replace(b"\n", b"")
                self.write({
                    'github_id': str(repo_data.get('id', '')),
                    'date_connected': datetime.now(),
                    'description': repo_data.get('description', ''),
                    'url': repo_data.get('html_url', ''),
                    'avatar_url': repo_data.get('owner', {}).get('avatar_url', ''),
                    'images': image if avatar_url else False,
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
        self.ensure_one()
        if not self.is_connected:
            raise UserError(_("Repository is not connected. Please connect the repository first."))

        token = self.env.user.git_token
        base_url = self.env.company.github_instance_url or 'https://api.github.com'

        try:
            response = requests.get(
                f'{base_url}/repos/{self.owner}/{self.name}/branches',
                headers=self._header_authentication(),
                timeout=10
            )
            if response.status_code == 200:
                branches = response.json()
                existing_branch_names = self.branch_ids.mapped('name')
                new_branches = []
                for branch in branches:
                    if branch['name'] not in existing_branch_names:
                        new_branches.append((0, 0, {
                            'name': branch['name'],
                            'protected': branch.get('protected', False),
                        }))
                if new_branches:
                    self.write({'branch_ids': new_branches})
                    self.message_post(body=_("Synchronized branches successfully. Added %d new branches." % len(new_branches)))
                else:
                    self.message_post(body=_("No new branches to synchronize."))
            else:
                raise UserError(_("Failed to fetch branches from GitHub. Please check your connection and try again."))
        except requests.RequestException as e:
            raise UserError(_("An error occurred while fetching branches from GitHub: %s") % str(e))

    def action_delete_branch(self):
        pass

    @api.depends('branch_ids')
    def _compute_branch_count(self):
        for record in self:
            record.branch_count = len(record.branch_ids)

    def action_view_branches(self):
        """Open branches view."""
        self.ensure_one()
        return {
            'name': _('Branches'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.github.branch',
            'view_mode': 'list',
            'domain': [('repository_id', '=', self.id)],
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
                'duplicate': False,
            },
            'target': 'new',
        }
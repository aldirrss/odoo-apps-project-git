import requests
from datetime import datetime
from markupsafe import Markup
from odoo import fields, models, api, _
import base64
from odoo.exceptions import UserError


class ProjectGithubRepository(models.Model):
    _name = "project.github.repository"
    _description = "Project Github Repository"

    name = fields.Char(string="Repository Name", required=True)
    repository_id = fields.Char(string="ID", readonly=True)
    owner = fields.Char(string="Owner", required=True)
    description = fields.Text(string="Description", readonly=True)
    private = fields.Boolean(string="Private", readonly=True)
    full_name = fields.Char(string="Full Name", readonly=True)
    html_url = fields.Char(string="URL", readonly=True)
    clone_url = fields.Char(string="Clone URL", readonly=True)
    ssh_url = fields.Char(string="SSH URL", readonly=True)
    language = fields.Char(string="Primary Language", readonly=True)
    stars_count = fields.Integer(string="Stars", readonly=True)
    forks_count = fields.Integer(string="Forks", readonly=True)
    open_issues_count = fields.Integer(string="Open Issues", readonly=True)
    archive = fields.Boolean(string="Archived", readonly=True)
    disabled = fields.Boolean(string="Disabled", readonly=True)
    visibility = fields.Char(string="Visibility", readonly=True)
    created_at = fields.Datetime(string="Created At", readonly=True)
    updated_at = fields.Datetime(string="Updated At", readonly=True)

    default_branch_id = fields.Many2one(
        comodel_name="project.github.branch",
        string="Default Branch",
        readonly=True,
        ondelete="set null",
    )
    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Project",
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
    )
    is_connected = fields.Boolean(string="Is Connected", default=False)

    repository_info_html = fields.Html(
        string="Repository Info",
        compute="_compute_repository_info_html",
    )

    def _compute_display_name(self):
        for repo in self:
            repo.display_name = f"{repo.owner}/{repo.name}"

    def action_view_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.full_name,
            "res_model": "project.github.repository",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    @api.depends("repository_id")
    def _compute_repository_info_html(self):
        for record in self:
            fields_config = [
                {'label': 'Name', 'value': record.name or ''},
                {'label': 'ID', 'value': record.repository_id or ''},
                {'label': 'Owner', 'value': record.owner or ''},
                {'label': 'Description', 'value': record.description or ''},
                {'label': 'Private', 'value': 'Yes' if record.private else 'No'},
                {'label': 'Full Name', 'value': record.full_name or ''},
                {'label': 'URL', 'value': f'<a href="{record.html_url}" target="_blank">{record.html_url}</a>' if record.html_url else ''},
                {'label': 'Clone URL', 'value': record.clone_url or ''},
                {'label': 'SSH URL', 'value': record.ssh_url or ''},
                {'label': 'Primary Language', 'value': record.language or ''},
                {'label': 'Stars', 'value': record.stars_count or 0},
                {'label': 'Forks', 'value': record.forks_count or 0},
                {'label': 'Open Issues', 'value': record.open_issues_count or 0},
                {'label': 'Archived', 'value': 'Yes' if record.archive else 'No'},
                {'label': 'Disabled', 'value': 'Yes' if record.disabled else 'No'},
                {'label': 'Visibility', 'value': f'Public' if record.visibility == 'public' else ("Private" if record.visibility == "private" else record.visibility)},
                {'label': 'Created At', 'value': fields.Datetime.to_string(record.created_at) if record.created_at else ''},
                {'label': 'Updated At', 'value': fields.Datetime.to_string(record.updated_at) if record.updated_at else ''},
            ]
            html = '<table style="width: 100%; border-collapse: collapse; margin: 10px;">'
            for field_data in fields_config:
                html += f'''
                            <tr>
                                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; background-color: #f5f5f5; width: 200px;">
                                    {field_data['label']}
                                </td>
                                <td style="padding: 8px; border: 1px solid #ddd;">
                                    {field_data['value']}
                                </td>
                            </tr>
                            '''
            html += '</table>'
            record.repository_info_html = html

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

    def _compute_display_name(self):
        for repo in self:
            repo.display_name = f"{repo.owner}/{repo.name}"
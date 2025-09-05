from odoo import fields, models, api


class ProjectProject(models.Model):
    _inherit = "project.project"

    github_repository_id = fields.Many2one(
        comodel_name="project.github.repository",
        string="GitHub Repository",
        domain="[('project_id', '=', False)]",
        ondelete="set null",
        tracking=True,
    )

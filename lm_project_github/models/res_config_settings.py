from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_project_git = fields.Boolean(
        string='Enable Project Git Features',
        implied_group='lm_project_github.group_project_git',
    )
    github_instance_url = fields.Char(
        string='GitHub Instance URL',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_git_integration = fields.Boolean(
        string='Enable Git Integration',
        implied_group='lm_project_github.group_git_integration',
        help='Enable or disable Git integration features.',
    )
    enable_project_git = fields.Boolean(
        string='Project Git Integration',
        related='company_id.enable_project_git',
        readonly=False,
        help='Enable or disable project-specific Git features.',
    )
    github_instance_url = fields.Char(
        string='GitHub Instance URL',
        related='company_id.github_instance_url',
        readonly=False,
        help='The base URL of your GitHub instance.',
    )

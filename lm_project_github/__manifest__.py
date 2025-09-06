# -*- coding: utf-8 -*-
{
    'name': "Github Integration | Project Git Integration | Github Base | Github Connector",
    'summary': "Project Github, Github Webhook, Github Issues, Github Commits, Github Tasks, Github Integrate, Github Odoo, Github Base",
    'description': """This module integrates GitHub with Odoo's project management system, allowing users to link GitHub repositories, issues, and commits to their projects and tasks within Odoo. It provides seamless synchronization between GitHub and Odoo, enhancing collaboration and productivity for development teams.""",
    'author': "Lema Core Technologies",
    'website': "https://www.lemacore.com",
    'category': 'Project',
    'version': '1.0',
    'depends': ['base', 'project'],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',

        'wizard/res_users_git_credential_views.xml',
        'wizard/project_github_create_repository_views.xml',
        'views/project_github_repository_views.xml',
        'views/project_github_branch_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'lm_project_github/static/src/**/*.js',
            'lm_project_github/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 69.99,
    'currency': 'USD',
}


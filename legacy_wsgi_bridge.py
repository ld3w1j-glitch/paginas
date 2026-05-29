"""Ponte temporária para migrar apps Flask legados para Blueprints por etapas.

Os programas grandes ainda continuam como sub-aplicações WSGI para preservar
login, url_for(), templates e sessões. O Editor Admin, o Prompt Profissional e o Financeiro já foram convertidos
para Blueprint real e não passam mais por esta ponte.
"""

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

from curso_ingles_app.app import create_app as create_curso_app


def build_legacy_mounts():
    return {
        "/curso-ingles": create_curso_app(),
    }


def attach_legacy_apps(portal_app):
    """Monta os módulos existentes preservando as URLs atuais."""
    application = DispatcherMiddleware(portal_app, build_legacy_mounts())
    return ProxyFix(application, x_for=1, x_proto=1, x_host=1, x_prefix=1)

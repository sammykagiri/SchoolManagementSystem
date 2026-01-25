from django.apps import AppConfig


class ReceivablesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'receivables'
    
    def ready(self):
        """Import signals when app is ready"""
        import receivables.models  # noqa - This ensures signals are registered

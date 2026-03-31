from django.apps import AppConfig

class QuoteappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quoteapp'
    
    def ready(self):
        # Import signals when app is ready
        import quoteapp.signals



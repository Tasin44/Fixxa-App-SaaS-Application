from django.contrib import admin


from .models import Folder,ScannedDocument,Quote,QuoteItem,Invoice,InvoiceItem




admin.site.register(Folder)
admin.site.register(ScannedDocument)
admin.site.register(Quote)
admin.site.register(QuoteItem)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)




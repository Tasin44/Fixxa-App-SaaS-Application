
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from io import BytesIO
from decimal import Decimal
from reportlab.platypus import HRFlowable

# ✅ Create a reusable upload path function(DEEps)
def get_client_upload_path(instance, folder_name, filename):
    """
    Generic client upload path generator.

    Args:
        instance: Model instance (Quote, Invoice, etc.)
        folder_name: Sub-folder (e.g. "quotes", "invoices", "signatures/quotes")
        filename: Original filename uploaded

    Returns:
        str: Path where the file should be stored
    """
    if hasattr(instance, 'client') and instance.client:#checks if the instance object has the client field,This condition covers Quote (because a Quote must have a client).
        client = instance.client
    elif hasattr(instance, 'quote') and instance.quote:#This condition covers Invoice (because an Invoice must have a Quote, and that Quote has the client).
        client = instance.quote.client
    else:
        # fallback if no client found
        '''
        If the system can’t find a client (no client linked to the instance), the file will be saved under a fallback folder called orphan_files.
        '''
        return os.path.join("orphan_files", folder_name, filename)
    
    safe_name = f"{client.name.replace(' ', '_')}"#safe folder name like 12_John_Doe (ID_client name, spaces between client name replaced with _, like jhon doe will become jhon_doe.
    return os.path.join(
        "client_documents",# base folder
        str(client.user.id),# user’s ID (keeps files separated per user)
        safe_name,# client folder name generated based on his id and name
        folder_name,# e.g. "quotes" / "invoices" / "signatures"
        filename#filename is the original file name uploaded by the user (e.g. invoice.pdf, signature.png).
    )

'''
❓❓❓why I'm using os.path.jon with the line -  return get_client_upload_path(instance, os.path.join("signatures", "quotes"), filename)? 

folder_name is expected to be one string.
but I'm using os.path.join("signatures", "quotes") means pre-joining the two subfolders named signatures and quotes into one string.
That's why I've to use os.path.join,That way it fits into the single folder_name parameter.

but I didn't use here os.path.join -  return get_client_upload_path(instance, "invoices", filename)
because "invoices" is just one folder, so you don’t need to os.path.join.It’s already a single string.

operating system.path.join or os.path.join is safely build file system paths that work across operating systems.


✅✅✅If I don't want to use os.path.join-

def get_client_upload_path(instance, folder_name, filename):
    return os.path.join(
        "client_documents",
        str(client.user.id),
        safe_name,
        *folders,
        filename
    )

Then I can use
def quote_signature_upload_path(instance, filename):
    return get_client_upload_path(instance, "signatures", "quotes", filename=filename)

'''



#================================================================================================================


#previous desing where Description, material , Qty , unit price , Duration, Rate , ammount present
# def generate_quote_pdf(quote):
#     """Generate a professional PDF for the quote"""
    
#     # Create PDF in memory
#     buffer = BytesIO()
#     doc = SimpleDocTemplate(buffer, pagesize=letter)
#     elements = []
#     styles = getSampleStyleSheet()
    
#     # Title
#     title_style = ParagraphStyle(
#         'CustomTitle',
#         parent=styles['Heading1'],
#         fontSize=24,
#         textColor=colors.HexColor('#2c3e50'),
#         spaceAfter=30,
#     )
#     elements.append(Paragraph(f"QUOTE #{quote.quote_number}", title_style))
#     elements.append(Spacer(1, 0.3*inch))
    
#     # Company and Client Info Side by Side
#     info_data = [
#         ['From:', 'To:'],
#         [quote.user.email, quote.client.name],
#         ['', quote.client.email or ''],
#         ['', quote.client.phone_number or ''],
#         ['', quote.client.address or ''],
#     ]
#     info_table = Table(info_data, colWidths=[3*inch, 3*inch])
#     info_table.setStyle(TableStyle([
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, -1), 10),
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#     ]))
#     elements.append(info_table)
#     elements.append(Spacer(1, 0.3*inch))
    
#     # Quote Details
#     details_data = [
#         ['Issue Date:', str(quote.issue_date)],
#         ['Due Date:', str(quote.due_date)],
#         ['Service Location:', quote.effective_service_location or 'N/A'],
#     ]
#     details_table = Table(details_data, colWidths=[2*inch, 4*inch])
#     details_table.setStyle(TableStyle([
#         ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, -1), 10),
#     ]))
#     elements.append(details_table)
#     elements.append(Spacer(1, 0.4*inch))
    
#     # Items Table Header
#     items_data = [['Description', 'Material', 'Qty', 'Unit Price', 'Duration', 'Rate', 'Amount']]
    

#     # Add each quote item
#     for item in quote.items.all():
#         # ✅ Calculate total amount for this item (material cost + service cost)
#         material_cost = item.quantity * item.unit_price
#         service_cost = item.service_duration * item.service_rate
#         item_total = material_cost + service_cost
        
#         items_data.append([
#             item.quote_description or '',
#             item.material_name or '',
#             str(item.quantity),
#             f"£{item.unit_price}",
#             f"{item.service_duration} {item.duration_unit}",
#             f"£{item.service_rate}",
#             f"£{item_total}",  # ✅ Calculated amount
#         ])
    
#     # Create items table
#     items_table = Table(items_data, colWidths=[1.5*inch, 1*inch, 0.5*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.8*inch])
#     items_table.setStyle(TableStyle([
#         # Header row styling
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('FONTSIZE', (0, 0), (-1, 0), 10),
#         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        
#         # Data rows styling
#         ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
#         ('FONTSIZE', (0, 1), (-1, -1), 9),
#         ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
#         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#     ]))
#     elements.append(items_table)
#     elements.append(Spacer(1, 0.3*inch))
    
#     # Totals Section
#     totals_data = [
#         ['Subtotal:', f"£{quote.subtotal}"],
#         ['VAT ({}%):'.format(quote.vat_rate), f"£{quote.subtotal * quote.vat_rate / Decimal('100')}"],
#     ]
    
#     # Add discount if applicable
#     if quote.discount_amount > 0:
#         discount_label = f"Discount ({quote.discount_amount}{'%' if quote.discount_type == 'percentage' else ''})"
#         if quote.discount_type == 'percentage':
#             discount_value = quote.subtotal * (quote.discount_amount / Decimal('100'))
#         else:
#             discount_value = quote.discount_amount
#         totals_data.append([f"{discount_label}:", f"-£{discount_value}"])
    
#     totals_data.append(['TOTAL:', f"£{quote.total}"])
    
#     totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch], hAlign='RIGHT')
#     totals_table.setStyle(TableStyle([
#         ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
#         ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Total row bold
#         ('FONTSIZE', (0, 0), (-1, -1), 11),
#         ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
#         ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),  # Line above total
#     ]))
#     elements.append(totals_table)
    
#     # Build PDF
#     doc.build(elements)
    
#     # Return PDF bytes
#     pdf_bytes = buffer.getvalue()
#     buffer.close()
#     return pdf_bytes


# #This desing also working perfectluy 
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from io import BytesIO
from decimal import Decimal

def generate_quote_pdf(quote):
    """Generate a modern quote PDF styled exactly like the reference image"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    elements = []
    styles = getSampleStyleSheet()

    # =========================
    # HEADER: "QUOTE" centered + "Fixxa" left-aligned below it
    # =========================
    quote_title_style = ParagraphStyle(
        'QuoteTitle',
        fontSize=28,
        textColor=colors.HexColor('#1f4fd8'),
        alignment=1,  # center
        spaceAfter=2,
        fontName='Helvetica-Bold'
    )
    company_style = ParagraphStyle(
        'Company',
        fontSize=12,
        textColor=colors.HexColor('#555555'),
        alignment=0,  # left
        spaceAfter=12,
        fontName='Helvetica'
    )

    elements.append(Paragraph("QUOTE", quote_title_style))
    #elements.append(Paragraph("<b>≡ Fixxa</b>", company_style))  # Simulate logo with ≡
    # Attractive Fixxa heading
    # fixxa_style = ParagraphStyle(
    #     'FixxaBrand',
    #     fontSize=36,
    #     # textColor=colors.HexColor('#1f4fd8'),
    #     # fontName='Helvetica-Bold',
    #     # alignment=0,
    #     # spaceAfter=4,
    #         textColor=colors.black,      # ✅ black color
    #         fontName='Helvetica-Bold',   # ✅ bold
    #         alignment=0,
    #         spaceAfter=12,               # little spacing below
    # )
    # elements.append(Paragraph("Fixxa", fixxa_style))

    # Underline bar (80 points wide = ~1.1 inches)
    # from reportlab.platypus import HRFlowable
    # elements.append(HRFlowable(
    #     color=colors.HexColor('#1f4fd8'),
    #     thickness=2,
    #     width=80,          # ← number, not string with 'px'
    #     spaceBefore=0,
    #     spaceAfter=12
    # ))

    # =========================
    # QUOTE INFO ROW: Quote No, Issue Date, Due Date
    # =========================
    info_data = [
        [
            Paragraph(f"<b>Quote No:</b> {quote.quote_number}", styles['Normal']),
            Paragraph(
                f"<b>Issue Date:</b> {quote.issue_date}<br/>"
                f"<b>Due Date:</b> {quote.due_date}",
                styles['Normal']
            )
        ]
    ]

    info_table = Table(info_data, colWidths=[3.5 * inch, 2.5 * inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafd')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3 * inch))

    # =========================
    # FROM / TO SECTION (Two-column table)
    # =========================
    from_to_data = [
        [Paragraph("<b>From</b>", styles['Normal']), Paragraph("<b>To</b>", styles['Normal'])],
        [quote.user.email, quote.client.name],
        ["", quote.client.email or ""],
        ["", quote.client.phone_number or ""],
        ["", quote.client.address or ""],
    ]

    from_to_table = Table(from_to_data, colWidths=[3 * inch, 3 * inch])
    from_to_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f4ff')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(from_to_table)
    elements.append(Spacer(1, 0.35 * inch))

    # =========================
    # ITEMS TABLE (Preserve original column names)
    # =========================
    items_data = [
        ['Description', 'Qty', 'Unit Price', 'Service', 'Amount']
    ]

    for item in quote.items.all():
        material_cost = item.quantity * item.unit_price
        service_cost = item.service_duration * item.service_rate
        item_total = material_cost + service_cost

        items_data.append([
            item.quote_description or '',
            str(item.quantity),
            f"£{item.unit_price:.2f}",
            f"{item.service_duration} {item.duration_unit}",
            f"£{item_total:.2f}",
        ])

    items_table = Table(
        items_data,
        colWidths=[2.4 * inch, 0.6 * inch, 1 * inch, 1 * inch, 1 * inch]
    )

    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4fd8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafd')]),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))

    # =========================
    # TOTALS (Right-aligned, styled like screenshot)
    # =========================
    vat_amount = quote.subtotal * quote.vat_rate / Decimal('100')

    totals_data = [
        ['Subtotal', f"£{quote.subtotal:.2f}"],
        [f"VAT ({quote.vat_rate}%)", f"£{vat_amount:.2f}"],
    ]

    if quote.discount_amount > 0:
        discount_value = (
            quote.subtotal * (quote.discount_amount / Decimal('100'))
            if quote.discount_type == 'percentage'
            else quote.discount_amount
        )
        totals_data.append(['Discount', f"-£{discount_value:.2f}"])

    totals_data.append(['TOTAL DUE', f"£{quote.total:.2f}"])

    totals_table = Table(
        totals_data,
        colWidths=[3.5 * inch, 1.5 * inch],
        hAlign='RIGHT'
    )

    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8fafd')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1f4fd8')),
    ]))

    elements.append(totals_table)

    # =========================
    # BUILD PDF
    # =========================
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes






def generate_invoice_pdf(invoice):
    """Generate a professional PDF for the invoice"""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
    )
    elements.append(Paragraph(f"INVOICE #{invoice.invoice_number}", title_style))
    elements.append(Spacer(1, 0.3*inch))

    # Company and Client Info
    info_data = [
        ['From:', 'To:'],
        [invoice.user.email, invoice.client.name],
        ['', invoice.client.email or ''],
        ['', invoice.client.phone_number or ''],
        ['', invoice.client.address or ''],
    ]
    info_table = Table(info_data, colWidths=[3*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))

    # Invoice Details
    details_data = [
        ['Issue Date:', str(invoice.issue_date)],
        ['Due Date:', str(invoice.due_date)],
        ['Service Location:', invoice.effective_service_location or 'N/A'],
    ]
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.4*inch))

    # Items Table Header
    items_data = [['quote_description', 'Material', 'Qty', 'Unit Price', 'Duration', 'Rate', 'Amount']]

    # Add each invoice item
    for item in invoice.items.all():
        material_cost = item.quantity * item.unit_price
        service_cost = item.service_duration * item.service_rate
        item_total = material_cost + service_cost

        items_data.append([
            item.quote_description or '',
            item.material_name or '',
            str(item.quantity),
            f"£{item.unit_price}",
            f"{item.service_duration} {item.duration_unit}",
            f"£{item.service_rate}",
            f"£{item_total}",
        ])

    # Items table styling
    items_table = Table(items_data, colWidths=[1.5*inch, 1*inch, 0.5*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.8*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))

    # Totals Section
    totals_data = [
        ['Subtotal:', f"£{invoice.subtotal}"],
        ['VAT ({}%):'.format(invoice.vat_rate), f"£{invoice.subtotal * invoice.vat_rate / Decimal('100')}"],
    ]

    # Discount if applicable
    if invoice.discount_amount > 0:
        discount_label = f"Discount ({invoice.discount_amount}{'%' if invoice.discount_type == 'percentage' else ''})"
        if invoice.discount_type == 'percentage':
            discount_value = invoice.subtotal * (invoice.discount_amount / Decimal('100'))
        else:
            discount_value = invoice.discount_amount
        totals_data.append([discount_label + ':', f"-£{discount_value}"])

    totals_data.append(['TOTAL:', f"£{invoice.total}"])

    totals_table = Table(totals_data, colWidths=[5*inch, 1.5*inch], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    elements.append(totals_table)

    # Build PDF
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes



























# """Natural language to SQL chatbot"""

# import logging
# from langchain_openai import ChatOpenAI
# from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
# from .clients import AIClients
# from .config import Config
# from .utils import validate_user_id

# logger = logging.getLogger(__name__)


# def get_database_schema(user_id: str) -> str:
#     """
#     Get database schema for user's accessible tables.
    
#     Args:
#         user_id: User UUID for row-level security
    
#     Returns:
#         str: Database schema information
#     """
#     try:
#         validate_user_id(user_id)
#         db = AIClients.get_database()
        
#         # Get schema information
#         schema = db.get_table_info()
#         logger.info(f"Retrieved database schema for user: {user_id[:8]}")
        
#         return schema
    
#     except Exception as e:
#         logger.error(f"Failed to get database schema: {e}")
#         raise


# def natural_language_query(user_id: str, question: str) -> dict:
#     """
#     Convert natural language question to SQL and execute.
    
#     This implements row-level security by automatically adding
#     WHERE user_id = '{user_id}' to all queries.
    
#     Args:
#         user_id: User UUID (from Django request.user.id)
#         question: Natural language question about the database
    
#     Returns:
#         dict: {
#             'success': bool,
#             'sql_query': str,
#             'result': list,
#             'answer': str,
#             'error': str (if failed)
#         }
    
#     Example:
#         >>> result = natural_language_query(
#         ...     user_id="fa830eb7-310e-4f9f-bb35-dff1d77e072d",
#         ...     question="How many clients do I have?"
#         ... )
#         >>> print(result['answer'])
#     """
#     try:
#         # Validate user_id
#         validate_user_id(user_id)
        
#         # Get database and LLM
#         db = AIClients.get_database()
#         llm = ChatOpenAI(
#             model=Config.SQL_MODEL,
#             temperature=0,
#             api_key=Config.OPENAI_API_KEY
#         )
        
#         # Create prompt for SQL generation
#         sql_prompt = f"""Given the database schema below, write a SQL query to answer the question.

# Database Schema:
# {db.get_table_info()}

# Question: {question}

# CRITICAL SECURITY RULE: Always add WHERE user_id = '{user_id}' to filter data.

# Return only the SQL query, nothing else."""

#         # Generate SQL query
#         response = llm.invoke(sql_prompt)
#         sql_query = response.content.strip()
        
#         # Clean up SQL (remove markdown code blocks if present)
#         if sql_query.startswith('```'):
#             sql_query = sql_query.split('```')[1]
#             if sql_query.startswith('sql'):
#                 sql_query = sql_query[3:]
#             sql_query = sql_query.strip()
        
#         logger.info(f"Generated SQL: {sql_query[:100]}...")
        
#         # Execute query
#         execute_tool = QuerySQLDataBaseTool(db=db)
#         result = execute_tool.invoke(sql_query)
        
#         # Generate natural language answer
#         answer_prompt = f"""
#         Question: {question}
#         SQL Query: {sql_query}
#         Result: {result}
        
#         Provide a clear, concise answer in natural language.
#         """
        
#         answer_response = llm.invoke(answer_prompt)
#         answer = answer_response.content
        
#         logger.info(f"Query successful for user: {user_id[:8]}")
        
#         return {
#             'success': True,
#             'sql_query': sql_query,
#             'result': result,
#             'answer': answer
#         }
    
#     except Exception as e:
#         logger.error(f"Natural language query failed: {e}")
#         return {
#             'success': False,
#             'error': str(e)
#         }

"""Natural language chatbot using Django ORM instead of raw SQL"""

import logging
from .clients import AIClients
from .config import Config
from .utils import validate_user_id

logger = logging.getLogger(__name__)


def natural_language_query(user_id: str, question: str) -> dict:
    try:
        validate_user_id(user_id)

        # Import Django models here to avoid circular imports
        from quoteapp.models import Quote, Invoice, QuoteItem, InvoiceItem
        from clientapp.models import Client
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        from datetime import datetime

        # Build context data from Django ORM
        now = timezone.now()
        current_month = now.month
        current_year = now.year

        # Fetch stats for this user
        quotes_this_month = Quote.objects.filter(
            user_id=user_id,
            created_at__month=current_month,
            created_at__year=current_year
        ).count()

        invoices_this_month = Invoice.objects.filter(
            user_id=user_id,
            created_at__month=current_month,
            created_at__year=current_year
        ).count()

        total_quotes = Quote.objects.filter(user_id=user_id).count()
        total_invoices = Invoice.objects.filter(user_id=user_id).count()
        total_clients = Client.objects.filter(user_id=user_id).count()

        unpaid_invoices = Invoice.objects.filter(
            user_id=user_id,
            payment_status='unpaid'
        ).count()

        paid_invoices = Invoice.objects.filter(
            user_id=user_id,
            payment_status='paid'
        ).count()

        draft_quotes = Quote.objects.filter(
            user_id=user_id,
            quote_status='draft'
        ).count()

        accepted_quotes = Quote.objects.filter(
            user_id=user_id,
            quote_status='accepted'
        ).count()

        total_invoice_value = Invoice.objects.filter(
            user_id=user_id
        ).aggregate(total=Sum('total'))['total'] or 0

        paid_invoice_value = Invoice.objects.filter(
            user_id=user_id,
            payment_status='paid'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Build context string for LLM
        context = f"""
User's business data summary:
- Total Clients: {total_clients}
- Total Quotes: {total_quotes} (Draft: {draft_quotes}, Accepted: {accepted_quotes})
- Total Invoices: {total_invoices} (Unpaid: {unpaid_invoices}, Paid: {paid_invoices})
- Quotes created this month ({now.strftime('%B %Y')}): {quotes_this_month}
- Invoices created this month ({now.strftime('%B %Y')}): {invoices_this_month}
- Total Invoice Value: £{total_invoice_value:,.2f}
- Paid Invoice Value: £{paid_invoice_value:,.2f}
- Outstanding Value: £{float(total_invoice_value) - float(paid_invoice_value):,.2f}
"""

        # Ask LLM to answer based on context
        llm_client = AIClients.get_openai_client()

        response = llm_client.chat.completions.create(
            model=Config.GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful business assistant. Answer questions based on the provided business data. Be concise and friendly."
                },
                {
                    "role": "user",
                    "content": f"Business Data:\n{context}\n\nQuestion: {question}"
                }
            ]
        )

        answer = response.choices[0].message.content

        return {
            'success': True,
            'answer': answer,
            'context': context.strip()
        }

    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
# # notification/firebase_config.py
# import firebase_admin
# from firebase_admin import credentials, messaging
# from django.conf import settings
# import logging

# logger = logging.getLogger(__name__)

# # Initialize Firebase (add to settings.py: FIREBASE_CREDENTIALS_PATH)
# #will uncomment this below two line after getting the json file from izaz
# # cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
# # firebase_admin.initialize_app(cred)

# def send_fcm_notification(user, title, body, notification_type, extra_data=None):
#     """Send FCM notification to all user's devices"""
#     from .models import DeviceToken, Notification
    
#     # Save notification in DB
#     notification = Notification.objects.create(
#         user=user,
#         notification_type=notification_type,
#         title=title,
#         body=body,
#         data=extra_data or {}
#     )
    
#     # Get active device tokens
#     tokens = list(user.device_tokens.filter(is_active=True).values_list('token', flat=True))
    
#     if not tokens:
#         logger.warning(f"No FCM tokens for user {user.id}")
#         return False
    
#     # Prepare message
#     message = messaging.MulticastMessage(
#         notification=messaging.Notification(title=title, body=body),
#         data={
#             'notification_type': notification_type,
#             'notification_id': str(notification.id),
#             **(extra_data or {})
#         },
#         tokens=tokens,
#     )
    
#     try:
#         response = messaging.send_multicast(message)
#         logger.info(f"FCM sent: {response.success_count}/{len(tokens)} successful")
        
#         # Deactivate failed tokens
#         if response.failure_count > 0:
#             failed_tokens = [tokens[idx] for idx, resp in enumerate(response.responses) if not resp.success]
#             DeviceToken.objects.filter(token__in=failed_tokens).update(is_active=False)
        
#         return True
#     except Exception as e:
#         logger.error(f"FCM error: {str(e)}")
#         return False
    

    
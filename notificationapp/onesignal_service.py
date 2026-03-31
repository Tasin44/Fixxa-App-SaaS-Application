import requests
import logging
from django.conf import settings
# from notificationapp.models import DeviceToken
from notificationapp.models import DeviceToken

logger = logging.getLogger(__name__)


def send_onesignal_notification(user, title: str, body: str, data: dict = None):
    """
    Send push notification via OneSignal to a specific user.
    
    OneSignal identifies users by external_user_id (we use user.id).
    Flutter SDK must call:
        OneSignal.login(userId.toString())  → sets external_user_id
    """
    try:
        # Get all active device tokens for this user
        # device_tokens = DeviceToken.objects.filter(user=user, is_active=True).values_list('token', flat=True)
        
        # if not device_tokens:
        #     logger.warning(f"No device tokens found for user {user.id}")
        #     return {"error": "No device tokens found"}
        # Use saved subscription IDs directly
        device_tokens = list(DeviceToken.objects.filter(user=user, is_active=True).values_list('token', flat=True))
        
        if not device_tokens:
            logger.warning(f"No device tokens found for user {user.id}")
            return {"error": "No device tokens found"}
        
        headers = {
            "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
            "Content-Type": "application/json",
        }

        
        payload = {
            "app_id": settings.ONESIGNAL_APP_ID,
            # "include_aliases": {
            #     "external_id": [str(user.id)]   # must match what Flutter sets
            # },
            "include_subscription_ids": device_tokens,  # ✅ use subscription ID directly
            "target_channel": "push",
            "headings": {"en": title},
            "contents": {"en": body},
            "data": data or {},
        }

        response = requests.post(
            "https://onesignal.com/api/v1/notifications",
            headers=headers,
            json=payload,
            timeout=10
        )

        result = response.json()
        if response.status_code == 200 and result.get("recipients", 0) > 0:
            logger.info(f"OneSignal notification sent to user {user.id}: {title}")
        else:
            logger.warning(f"OneSignal response for user {user.id}: {result}")

        return result

    except Exception as e:
        logger.error(f"OneSignal notification failed for user {user.id}: {e}")
        return None

# import requests
# import logging
# from django.conf import settings
# from notificationapp.models import DeviceToken

# logger = logging.getLogger(__name__)


# def send_onesignal_notification(user, title: str, body: str, data: dict = None):
#     try:
#         device_tokens = DeviceToken.objects.filter(user=user, is_active=True).values_list('token', flat=True)
        
#         if not device_tokens:
#             logger.warning(f"No device tokens found for user {user.id}")
#             return {"error": "No device tokens found"}

#         headers = {
#             "Authorization": f"key={settings.FCM_SERVER_KEY}",  # Firebase Server Key
#             "Content-Type": "application/json",
#         }

#         results = []
#         for token in device_tokens:
#             payload = {
#                 "to": token,  # FCM token directly
#                 "notification": {
#                     "title": title,
#                     "body": body,
#                 },
#                 "data": data or {},
#             }

#             response = requests.post(
#                 "https://fcm.googleapis.com/fcm/send",
#                 headers=headers,
#                 json=payload,
#                 timeout=10
#             )
#             result = response.json()
#             logger.info(f"FCM response for user {user.id}: {result}")
#             results.append(result)

#         return {"success": True, "results": results}

#     except Exception as e:
#         logger.error(f"FCM notification failed for user {user.id}: {e}")
#         return None
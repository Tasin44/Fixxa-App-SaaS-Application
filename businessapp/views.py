import stripe
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated,AllowAny

User = get_user_model()
from rest_framework.response import Response
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import BusinessProfile
stripe.api_key = settings.STRIPE_SECRET_KEY  # Add to settings.py
from rest_framework.views import APIView
from rest_framework import status
from .serializers import BusinessProfileCreateUpdateSerializer
from rest_framework.parsers import MultiPartParser, FormParser


class BusinessProfileCreateUpdateView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]  # 👈 Add this line

    def post(self, request):
        """Create or update business profile after signup"""
        # user = request.user
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({
                "success": False,
                "statusCode": status.HTTP_400_BAD_REQUEST,
                "message": "user_id is required.",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(id=user_id, verified=True)
        except User.DoesNotExist:
            return Response({
                "success": False,
                "statusCode": status.HTTP_404_NOT_FOUND,
                "message": "User not found or not verified.",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get or create business profile
        business, created = BusinessProfile.objects.get_or_create(user=user)
        
        # Update with user data
        serializer = BusinessProfileCreateUpdateSerializer(
            business, 
            data=request.data, 
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "statusCode": status.HTTP_200_OK,
                "message": "Business profile saved successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            "success": False,
            "statusCode": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data.",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        """Get current user's business profile"""
        try:
            business = request.user.business_profile
            serializer = BusinessProfileCreateUpdateSerializer(business)
            return Response({
                "success": True,
                "statusCode": status.HTTP_200_OK,
                "message": "Business profile retrieved.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except BusinessProfile.DoesNotExist:
            return Response({
                "success": False,
                "statusCode": status.HTTP_404_NOT_FOUND,
                "message": "Business profile not found.",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)
        
    def patch(self, request):
        """Partially update business profile"""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({
                "success": False,
                "statusCode": status.HTTP_400_BAD_REQUEST,
                "message": "user_id is required.",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id, verified=True)
        except User.DoesNotExist:
            return Response({
                "success": False,
                "statusCode": status.HTTP_404_NOT_FOUND,
                "message": "User not found or not verified.",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            business = BusinessProfile.objects.get(user=user)
        except BusinessProfile.DoesNotExist:
            return Response({
                "success": False,
                "statusCode": status.HTTP_404_NOT_FOUND,
                "message": "Business profile not found.",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = BusinessProfileCreateUpdateSerializer(
            business,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "statusCode": status.HTTP_200_OK,
                "message": "Business profile updated successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "statusCode": status.HTTP_400_BAD_REQUEST,
            "message": "Invalid data.",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)



def is_stripe_supported_country(country_code):
    # Country specs list is authoritative and up-to-date
    try:
        specs = stripe.CountrySpec.retrieve(country_code)  # raises if not supported
        return True
    # except stripe.error.InvalidRequestError:
    except stripe.InvalidRequestError:
        return False
    
def is_stripe_onboarding_complete(account_id):
    try:
        account = stripe.Account.retrieve(account_id)
        return account.charges_enabled and account.details_submitted
    except:
        return False


'''
#old1
# @api_view(['GET'])
@permission_classes([IsAuthenticated])
def stripe_connect_onboard(request):
    """
    Redirect business user to Stripe Connect onboarding link
    """
    user = request.user
    business = request.user.business_profile


    if business.stripe_connected:
        return Response({"message": "Already connected"}, status=200)
    
    # ✅ Step 1: If user already has a Stripe account, reuse it
    if business.stripe_account_id:
        account_id = business.stripe_account_id
        try:
            account = stripe.Account.retrieve(account_id)
        except stripe.error.InvalidRequestError:
            # account may not exist or was deleted
            # ✅ Get country from request
            country = request.data.get('country', 'GB').upper()#request.data only works with POST/PUT/PATCH requests
            #country = request.query_params.get('country') # works for only GET 
            if not is_stripe_supported_country(country):

                return Response(
                    {"error": f"{country} is not supported for Stripe Connect."},
                    status=400)
            account = stripe.Account.create(

                type="express",
                country=country,
                email=request.user.email,
                capabilities={  # Add this block
                'card_payments': {'requested': True},
                'transfers': {'requested': True}
            }
            )

            business.stripe_account_id = account.id
            business.save()

    # ✅ Step 2: Create new one only if needed
    else: 
            country = request.data.get('country', 'GB').upper()#request.data only works with POST/PUT/PATCH requests
            #country = request.query_params.get('country') # works for only GET 
            if not is_stripe_supported_country(country):

                return Response(
                    {"error": f"{country} is not supported for Stripe Connect."},
                    status=400)
            account = stripe.Account.create(
                type="express",
                country=country,
                email=request.user.email,
                capabilities={  # Add this block
                'card_payments': {'requested': True},
                'transfers': {'requested': True}
            }
            )
            business.stripe_account_id = account.id
            business.save()        

    account_link = stripe.AccountLink.create(
        account=account.id,
        type='account_onboarding',


        # refresh_url=f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error&account_id={account.id}",
        # return_url=f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success&account_id={account.id}"
    refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account.id}",
    return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account.id}"

    )
    # ✅ If user opened onboarding in browser (GET request) -> redirect to Stripe
    if request.method == "GET":
        return redirect(account_link.url)
    # ✅ Return URL instead of redirect (better for API testing)
    return Response({
        "onboarding_url": account_link.url,
        "account_id": account.id,
        "message": "Open onboarding_url in browser to complete setup"
    })


'''


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def stripe_connect_onboard(request):
    user = request.user
    business = request.user.business_profile

    if business.stripe_connected:
        return Response({"message": "Already connected"}, status=200)
    
    # ✅ Get country from request (works for both GET and POST)
    if request.method == 'POST':
        country = request.data.get('country', 'GB').upper()## Defaults to 'GB' if no country provided 
    else:
        country = request.GET.get('country', 'GB').upper()
    
    # ✅ Step 1: If user already has a Stripe account, reuse it
    if business.stripe_account_id:
        account_id = business.stripe_account_id
        try:
            account = stripe.Account.retrieve(account_id)
        except stripe.error.InvalidRequestError:
            # Account doesn't exist, create new one
            if not is_stripe_supported_country(country):
                return Response(
                    {"error": f"{country} is not supported for Stripe Connect."},
                    status=400
                )
            '''
            Now this creates a brand-new Stripe Express account every time when user click onboarding URL
            '''
            account = stripe.Account.create(
                type="express",
                country=country,
                email=request.user.email,
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True}
                }
            )
            business.stripe_account_id = account.id
            business.save()
            account_id = account.id

    # ✅ Step 2: Create new account if needed
    else:
        if not is_stripe_supported_country(country):
            return Response(
                {"error": f"{country} is not supported for Stripe Connect."},
                status=400
            )
        '''
            Now this creates a brand-new Stripe Express account every time when user click onboarding URL
        '''
        account = stripe.Account.create(
            type="express",
            country=country,
            email=request.user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True}
            }
        )
        business.stripe_account_id = account.id
        business.save()
        account_id = account.id

    # ✅ Step 3: Create onboarding link
    account_link = stripe.AccountLink.create(
        account=account_id,
        type='account_onboarding',
        #--------------------------------------------------------------------------------
        #this below two url wrong because not containing account_id
        #refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/",
        #return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/"  
        #--------------------------------------------------------------------------------

        refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account_id}",#If the user cancels or the session expires, Stripe redirects them here so they can restart onboarding.
        return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account_id}"#After the user completes onboarding successfully, Stripe redirects them here to confirm completion in your app.
    )

    # ✅ Redirect for browser requests
    if request.method == "GET":
        return redirect(account_link.url)
    
    # ✅ Return JSON for API requests
    return Response({
        "onboarding_url": account_link.url,
        "account_id": account_id,
        "message": "Open onboarding_url in browser to complete setup"
    })

'''
#old 3
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stripe_connect_onboard(request):
    user = request.user
    business = request.user.business_profile

    try:
        # ✅ Step 0: Optional user-provided Stripe account ID
        provided_account_id = request.data.get('stripe_account_id')

        # ✅ Step 1: Use provided ID if available
        if provided_account_id:
            try:
                account = stripe.Account.retrieve(provided_account_id)
                business.stripe_account_id = provided_account_id
                business.stripe_connected = account.charges_enabled
                business.save()
                return Response({
                    "message": "Existing Stripe account connected successfully",
                    "account_id": provided_account_id
                })
            # except stripe.error.InvalidRequestError:
            except stripe.InvalidRequestError:
                return Response(
                    {"error": "Invalid Stripe account ID"},
                    status=400
                )

        # ✅ Step 2: If already connected
        if business.stripe_connected:
            return Response({"message": "Already connected"}, status=200)

        # ✅ Step 3: Use existing account if present
        if business.stripe_account_id:
            try:
                account = stripe.Account.retrieve(business.stripe_account_id)
            # except stripe.error.InvalidRequestError:
            except stripe.InvalidRequestError:
                account = None
        else:
            account = None

        # ✅ Step 4: If no valid account, create a new one
        if not account:
            country = request.data.get('country', 'GB').upper()
            if not is_stripe_supported_country(country):
                return Response(
                    {"error": f"{country} is not supported for Stripe Connect."},
                    status=400
                )

            account = stripe.Account.create(
                type="express",
                country=country,
                email=request.user.email,
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True}
                }
            )
            business.stripe_account_id = account.id
            business.save()

        # ✅ Step 5: Create onboarding link
        account_link = stripe.AccountLink.create(
            account=account.id,
            type='account_onboarding',
            refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account.id}",
            return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account.id}"
        )

        return Response({
            "onboarding_url": account_link.url,
            "account_id": account.id,
            "message": "Open onboarding_url in browser to complete setup"
        })
    except Exception as e:
        print("❌ Unexpected error in stripe_connect_onboard:", e)
        import traceback; traceback.print_exc()
        return Response({"error": str(e)}, status=500)
'''




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stripe_status(request):
    """Check Stripe connection status"""
    business = request.user.business_profile
    return Response({
        "success": True,
        "stripe_connected": business.stripe_connected,
        "stripe_connection_status": "connected" if business.stripe_connected else "not_connected",
        "stripe_account_id": business.stripe_account_id
    })

'''
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stripe_onboard_complete(request):
    """Verify onboarding completed"""
    business = request.user.business_profile
    
    if business.stripe_account_id:
        account = stripe.Account.retrieve(business.stripe_account_id)
        business.stripe_connected = account.charges_enabled
        business.save()
    
    # Redirect to your frontend
    # return redirect("{settings.BASE_URL}/dashboard?onboard=success")
    return redirect(f"{settings.BASE_URL}/dashboard?onboard=success")  # Add 'f' prefix

'''

# @api_view(['GET'])
# @permission_classes([AllowAny])  ## Allow Stripe redirect without login
# def stripe_onboard_complete(request):
#     """Verify onboarding completed - called by Stripe redirect"""
#     account_id = request.GET.get('account_id')
    
#     # if not account_id:
#     #     return redirect(f"{settings.BASE_URL}/dashboard?onboard=error")
#     if not account_id:
#         return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error")   
#     try:
#         # Find business profile by account_id
#         from businessapp.models import BusinessProfile
#         business = BusinessProfile.objects.get(stripe_account_id=account_id)
        
#         # Verify with Stripe
#         account = stripe.Account.retrieve(account_id)
#         '''
#         business.stripe_connected = account.charges_enabled
#         business.save()

#         ❌
#             Stripe will redirect even if the user didn't complete onboarding.
#             So the mistake was:
#             Treating the redirect as success instead of verifying Stripe status again after return.
#         '''

#         # Only success if truly enabled (onboarding done)
#         if account.charges_enabled and account.details_submitted:
#             business.stripe_connected = True
#             business.stripe_connection_date = timezone.now()
#             business.save()
#             return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success&account_id={account_id}")
#         else:
#             # Incomplete—prompt retry
#             return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=incomplete&account_id={account_id}")
        
#         # return redirect(f"{settings.BASE_URL}/dashboard?onboard=success")
#         # ✅ Include account_id in redirect back to dashboard
#         # return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success&account_id={account_id}")
#     except BusinessProfile.DoesNotExist:
#         # return redirect(f"{settings.BASE_URL}/dashboard?onboard=error")
#         return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error&account_id={account_id}")
#     except Exception as e:
#         # return redirect(f"{settings.BASE_URL}/dashboard?onboard=error")
#         return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error&account_id={account_id}")

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# def stripe_onboard_complete(request):
#     business = request.user.business_profile

#     if business.stripe_connected:
#         return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success")

#     # Create new onboarding URL always
#     account_id = business.stripe_account_id

#     if not account_id:
#         country = request.data.get('country', 'GB').upper()
#         account = stripe.Account.create(
#             type="express",
#             country=country,
#             email=request.user.email,
#             capabilities={
#                 "card_payments": {"requested": True},
#                 "transfers": {"requested": True},
#             },
#         )
#         business.stripe_account_id = account.id
#         business.save()
#     else:
#         account = stripe.Account.retrieve(account_id)

#     account_link = stripe.AccountLink.create(
#         account=account.id,
#         type="account_onboarding",
#         refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account.id}",
#         return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account.id}"
#     )

#     # # If the request is GET (user clicked button or reloaded) -> redirect user to Stripe onboarding
#     if request.method == "GET":
#         return redirect(account_link.url)

#     # If came from API POST -> send JSON
#     return Response({
#         "onboarding_url": account_link.url,
#         "account_id": account.id,
#         "message": "Open onboarding_url in browser to complete setup"
#     })

# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
# def stripe_onboard_complete(request):
#     business = request.user.business_profile
#     account_id = request.GET.get('account_id') or business.stripe_account_id
#     onboard = request.GET.get('onboard')

#     # Check if onboarding is actually complete
#     if account_id and onboard == 'success':
#         if is_stripe_onboarding_complete(account_id):
#             business.stripe_connected = True
#             business.stripe_details_submitted = True
#             business.stripe_connection_date = timezone.now()
#             business.save()
#             return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success")
    
#     # If not complete or error/refresh happened, create new onboarding URL
#     if not account_id:
#         country = request.data.get('country') or request.GET.get('country', 'GB').upper()
#         account = stripe.Account.create(
#             type="express",
#             country=country,
#             email=request.user.email,
#             capabilities={
#                 "card_payments": {"requested": True},
#                 "transfers": {"requested": True},
#             },
#         )
#         business.stripe_account_id = account.id
#         business.save()
#         account_id = account.id
    
#     # Create fresh onboarding link
#     account_link = stripe.AccountLink.create(
#         account=account_id,
#         type="account_onboarding",
#         refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account_id}",
#         return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account_id}"
#     )
    
#     # Always redirect to new onboarding URL
#     return redirect(account_link.url)

'''
# @api_view(['GET', 'POST'])
# @permission_classes([IsAuthenticated])
@permission_classes([AllowAny])
def stripe_onboard_complete(request):
    business = request.user.business_profile
    account_id = request.GET.get('account_id') or business.stripe_account_id
    onboard = request.GET.get('onboard')

    # ✅ Step 1: Check if onboarding is actually complete (success callback)
    if account_id and onboard == 'success':
        if is_stripe_onboarding_complete(account_id):
            business.stripe_connected = True
            business.stripe_details_submitted = True
            business.stripe_connection_date = timezone.now()
            business.save()
            return redirect('dashboard')  # or '/businessapp/dashboard/'
        else:
            # Success callback but not actually complete - treat as incomplete
            onboard = 'incomplete'

    
    # ✅ Step 2: If error, incomplete, or refresh - create new onboarding link
    if not account_id:
        # No account exists yet - shouldn't happen but handle it
        return redirect(f"{settings.BASE_URL}/businessapp/stripe/connect/")
    
    try:
        # Retrieve existing account
        account = stripe.Account.retrieve(account_id)
        
        # Create fresh onboarding link
        account_link = stripe.AccountLink.create(
            account=account_id,
            type="account_onboarding",
            refresh_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=error&account_id={account_id}",
            return_url=f"{settings.BASE_URL}/businessapp/stripe/onboard-complete/?onboard=success&account_id={account_id}"
        )
        
        # Redirect user back to Stripe onboarding
        return redirect(account_link.url)
        
    except stripe.error.InvalidRequestError:
        # Account doesn't exist anymore - start fresh
        return redirect(f"{settings.BASE_URL}/businessapp/stripe/connect/")

'''

    
@api_view(['GET'])  # Only GET for Stripe redirects
@permission_classes([AllowAny])
def stripe_onboard_complete(request):
    account_id = request.GET.get('account_id')
    if not account_id:
        return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error")
    
    try:
        business = BusinessProfile.objects.get(stripe_account_id=account_id)
        account = stripe.Account.retrieve(account_id)
        
        # Always verify—ignore params
        if account.charges_enabled and account.details_submitted:
            if not business.stripe_connected:
                business.stripe_connected = True
                business.stripe_connection_date = timezone.now()
                business.save()
            return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=success")
        else:
            # Reload/incomplete → dashboard incomplete (no new link here)
            return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=incomplete&account_id={account_id}")
    except BusinessProfile.DoesNotExist:
        return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error")
    except Exception as e:
        return redirect(f"{settings.BASE_URL}/businessapp/dashboard/?onboard=error")

'''
@login_required
def dashboard_view(request):
    """
    Simple dashboard to show Stripe onboarding status
    """
    onboard_status = request.GET.get('onboard')  # 'success' or 'error' from Stripe redirect
    context = {
        "onboard_status": onboard_status
    }
    return render(request, 'businessapp/dashboard.html', context)
'''
# @csrf_exempt  # Optional, avoids CSRF issues
# def dashboard_view(request):
#     business = request.user.business_profile
#     onboard_status = request.GET.get('onboard')
#     # account_id = request.GET.get('account_id')

#     # If user started onboarding but not finished, force resume
#     if business.stripe_account_id and not business.stripe_connected:
#         if not is_stripe_onboarding_complete(business.stripe_account_id):
#             return redirect("/businessapp/stripe/connect/")

#     context = {
#         "onboard_status": onboard_status,
#         # "account_id": account_id,
#         "account_id": business.stripe_account_id,
#     }
#     return render(request, 'businessapp/dashboard.html', context)

'''
@csrf_exempt  # Optional, avoids CSRF issues
def dashboard_view(request):
    business = request.user.business_profile
    onboard_status = request.GET.get('onboard')

    # If they have an account but haven't completed onboarding, redirect to continue
    if business.stripe_account_id and not business.stripe_connected:
        if not is_stripe_onboarding_complete(business.stripe_account_id):
            onboard_status = "incomplete"

    context = {
        "onboard_status": onboard_status,
        "account_id": business.stripe_account_id,
    }
    return render(request, 'businessapp/dashboard.html', context)
'''
@csrf_exempt
def dashboard_view(request):
    account_id = request.GET.get("account_id")

    # Case 1: Stripe redirect -> use account_id
    if account_id:
        try:
            business = BusinessProfile.objects.get(stripe_account_id=account_id)
        except BusinessProfile.DoesNotExist:
            return render(request, "businessapp/dashboard.html", {
                "onboard_status": "error",
                "account_id": None,
            })
    else:
        # Case 2: Normal dashboard access -> use logged in user
        if request.user.is_authenticated:
            try:
                business = request.user.business_profile
            except BusinessProfile.DoesNotExist:
                business = None
        else:
            business = None

    onboard_status = request.GET.get("onboard")

    context = {
        "onboard_status": onboard_status,
        "account_id": getattr(business, "stripe_account_id", None),
    }
    return render(request, 'businessapp/dashboard.html', context)


'''
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def connect_existing_stripe_account(request):
    account_id = request.data.get('stripe_account_id')
    business = BusinessProfile.objects.get(user=request.user)
    business.stripe_account_id = account_id
    business.save()
    return Response({"message": "Existing Stripe account linked successfully"})
'''




from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Payment, MpesaPayment, PaymentReceipt, PaymentReminder
from .mpesa_service import MpesaService
from communications.services import CommunicationService
from core.models import Student, StudentFee
import json
import uuid


@login_required
def payment_list(request):
    """List all payments"""
    school = request.user.profile.school
    payments = Payment.objects.filter(school=school).select_related(
        'student', 'student_fee__fee_category', 'student_fee__term'
    ).order_by('-payment_date')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        payments = payments.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(reference_number__icontains=search_query) |
            Q(transaction_id__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    # Filter by payment method
    method_filter = request.GET.get('method', '')
    if method_filter:
        payments = payments.filter(payment_method=method_filter)
    
    # Pagination
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'method_filter': method_filter,
    }
    
    return render(request, 'payments/payment_list.html', context)


@login_required
def payment_detail(request, payment_id):
    """Payment detail view"""
    school = request.user.profile.school
    payment = get_object_or_404(Payment, school=school, payment_id=payment_id)
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'payments/payment_detail.html', context)


@login_required
def initiate_mpesa_payment(request, student_fee_id):
    """Initiate M-Pesa payment"""
    school = request.user.profile.school
    student_fee = get_object_or_404(StudentFee, school=school, id=student_fee_id)
    
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        amount = request.POST.get('amount')
        
        if not phone_number or not amount:
            messages.error(request, 'Phone number and amount are required.')
            return redirect('core:student_detail', student_id=student_fee.student.student_id)
        
        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0.')
                return redirect('core:student_detail', student_id=student_fee.student.student_id)
            
            # Generate reference number
            reference = f"FEES{student_fee.student.student_id}{int(timezone.now().timestamp())}"
            
            # Initiate M-Pesa payment
            mpesa_service = MpesaService()
            result = mpesa_service.initiate_stk_push(
                phone_number=phone_number,
                amount=amount,
                reference=reference,
                student_fee_id=student_fee_id
            )
            
            if result['success']:
                messages.success(request, 'M-Pesa payment initiated. Please check your phone for the STK push.')
                return redirect('payments:payment_detail', payment_id=result['payment_id'])
            else:
                messages.error(request, f'Failed to initiate payment: {result["message"]}')
                
        except ValueError:
            messages.error(request, 'Invalid amount.')
        except Exception as e:
            messages.error(request, f'Error initiating payment: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'payments/initiate_mpesa_payment.html', context)


@login_required
def record_cash_payment(request, student_fee_id):
    """Record cash payment"""
    school = request.user.profile.school
    student_fee = get_object_or_404(StudentFee, school=school, id=student_fee_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        reference_number = request.POST.get('reference_number')
        notes = request.POST.get('notes', '')
        
        if not amount:
            messages.error(request, 'Amount is required.')
            return redirect('core:student_detail', student_id=student_fee.student.student_id)
        
        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0.')
                return redirect('core:student_detail', student_id=student_fee.student.student_id)
            
            # Create payment record
            payment = Payment.objects.create(
                school=school,
                student=student_fee.student,
                student_fee=student_fee,
                amount=amount,
                payment_method='cash',
                status='completed',
                reference_number=reference_number or f"CASH{int(timezone.now().timestamp())}",
                processed_by=request.user,
                notes=notes
            )
            
            # Update student fee
            student_fee.amount_paid += amount
            if student_fee.amount_paid >= student_fee.amount_charged:
                student_fee.is_paid = True
            student_fee.save()
            
            # Send receipt
            communication_service = CommunicationService()
            communication_service.send_payment_receipt(payment)
            
            messages.success(request, f'Cash payment of KES {amount} recorded successfully.')
            return redirect('payments:payment_detail', payment_id=payment.payment_id)
            
        except ValueError:
            messages.error(request, 'Invalid amount.')
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'payments/record_cash_payment.html', context)


@login_required
def record_bank_payment(request, student_fee_id):
    """Record bank transfer payment"""
    school = request.user.profile.school
    student_fee = get_object_or_404(StudentFee, school=school, id=student_fee_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        reference_number = request.POST.get('reference_number')
        transaction_id = request.POST.get('transaction_id')
        notes = request.POST.get('notes', '')
        
        if not amount or not reference_number:
            messages.error(request, 'Amount and reference number are required.')
            return redirect('core:student_detail', student_id=student_fee.student.student_id)
        
        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0.')
                return redirect('core:student_detail', student_id=student_fee.student.student_id)
            
            # Create payment record
            payment = Payment.objects.create(
                school=school,
                student=student_fee.student,
                student_fee=student_fee,
                amount=amount,
                payment_method='bank_transfer',
                status='completed',
                reference_number=reference_number,
                transaction_id=transaction_id,
                processed_by=request.user,
                notes=notes
            )
            
            # Update student fee
            student_fee.amount_paid += amount
            if student_fee.amount_paid >= student_fee.amount_charged:
                student_fee.is_paid = True
            student_fee.save()
            
            # Send receipt
            communication_service = CommunicationService()
            communication_service.send_payment_receipt(payment)
            
            messages.success(request, f'Bank payment of KES {amount} recorded successfully.')
            return redirect('payments:payment_detail', payment_id=payment.payment_id)
            
        except ValueError:
            messages.error(request, 'Invalid amount.')
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'payments/record_bank_payment.html', context)


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback"""
    if request.method == 'POST':
        try:
            # Parse callback data
            callback_data = json.loads(request.body)
            
            # Process the callback
            mpesa_service = MpesaService()
            success = mpesa_service.process_callback(callback_data)
            
            if success:
                # Send payment receipt
                checkout_request_id = callback_data.get('CheckoutRequestID')
                try:
                    mpesa_payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
                    payment = mpesa_payment.payment
                    
                    communication_service = CommunicationService()
                    communication_service.send_payment_receipt(payment)
                    
                except MpesaPayment.DoesNotExist:
                    pass
                
                return HttpResponse('OK', status=200)
            else:
                return HttpResponse('FAILED', status=400)
                
        except Exception as e:
            return HttpResponse(f'ERROR: {str(e)}', status=500)
    
    return HttpResponse('Method not allowed', status=405)


@login_required
def check_payment_status(request, payment_id):
    """Check M-Pesa payment status"""
    school = request.user.profile.school
    payment = get_object_or_404(Payment, school=school, payment_id=payment_id)
    
    if payment.payment_method == 'mpesa' and payment.status == 'processing':
        try:
            mpesa_payment = payment.mpesa_details
            mpesa_service = MpesaService()
            result = mpesa_service.check_transaction_status(mpesa_payment.checkout_request_id)
            
            if result['success']:
                return JsonResponse(result['data'])
            else:
                return JsonResponse({'error': result['message']}, status=400)
                
        except MpesaPayment.DoesNotExist:
            return JsonResponse({'error': 'M-Pesa payment details not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'status': payment.status})


@login_required
def payment_receipt_list(request):
    """List payment receipts"""
    school = request.user.profile.school
    receipts = PaymentReceipt.objects.filter(school=school).select_related(
        'student', 'payment'
    ).order_by('-issued_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=search_query) |
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(receipts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'payments/receipt_list.html', context)


@login_required
def generate_receipt(request, payment_id):
    """Generate payment receipt"""
    school = request.user.profile.school
    payment = get_object_or_404(Payment, school=school, payment_id=payment_id)
    
    # Check if receipt already exists
    if hasattr(payment, 'receipt'):
        messages.info(request, 'Receipt already exists for this payment.')
        return redirect('payments:payment_detail', payment_id=payment.payment_id)
    
    try:
        # Create receipt
        receipt = PaymentReceipt.objects.create(
            school=school,
            payment=payment,
            student=payment.student,
            amount_paid=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.get_payment_method_display(),
            fee_category=payment.student_fee.fee_category.name,
            term=f"{payment.student_fee.term.name} - {payment.student_fee.term.academic_year}",
            academic_year=payment.student_fee.term.academic_year,
            issued_by=request.user
        )
        
        messages.success(request, f'Receipt {receipt.receipt_number} generated successfully.')
        return redirect('payments:payment_detail', payment_id=payment.payment_id)
        
    except Exception as e:
        messages.error(request, f'Error generating receipt: {str(e)}')
        return redirect('payments:payment_detail', payment_id=payment.payment_id)


@login_required
def view_receipt(request, receipt_number):
    """View payment receipt"""
    school = request.user.profile.school
    receipt = get_object_or_404(PaymentReceipt, school=school, receipt_number=receipt_number)
    
    context = {
        'receipt': receipt,
    }
    
    return render(request, 'payments/view_receipt.html', context)


@login_required
def payment_reminder_list(request):
    """List payment reminders"""
    school = request.user.profile.school
    reminders = PaymentReminder.objects.filter(school=school).select_related(
        'student', 'student_fee__fee_category', 'student_fee__term'
    ).order_by('-created_at')
    
    # Filter by reminder type
    reminder_type = request.GET.get('type', '')
    if reminder_type:
        reminders = reminders.filter(reminder_type=reminder_type)
    
    # Pagination
    paginator = Paginator(reminders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'reminder_type': reminder_type,
    }
    
    return render(request, 'payments/reminder_list.html', context)


@login_required
def send_reminder(request, student_fee_id):
    """Send payment reminder"""
    school = request.user.profile.school
    student_fee = get_object_or_404(StudentFee, school=school, id=student_fee_id)
    
    if request.method == 'POST':
        reminder_type = request.POST.get('reminder_type')
        message = request.POST.get('message')
        send_email = request.POST.get('send_email') == 'on'
        send_sms = request.POST.get('send_sms') == 'on'
        
        try:
            # Create reminder record
            reminder = PaymentReminder.objects.create(
                school=school,
                student=student_fee.student,
                student_fee=student_fee,
                reminder_type=reminder_type,
                message=message
            )
            
            # Send communications
            communication_service = CommunicationService()
            
            if reminder_type == 'due_date_reminder':
                communication_service.send_due_date_reminder(student_fee, send_email, send_sms)
            elif reminder_type == 'overdue':
                communication_service.send_overdue_notice(student_fee, send_email, send_sms)
            
            # Update reminder status
            reminder.sent_via_email = send_email
            reminder.sent_via_sms = send_sms
            if send_email:
                reminder.email_sent_at = timezone.now()
            if send_sms:
                reminder.sms_sent_at = timezone.now()
            reminder.save()
            
            messages.success(request, 'Payment reminder sent successfully.')
            return redirect('core:student_detail', student_id=student_fee.student.student_id)
            
        except Exception as e:
            messages.error(request, f'Error sending reminder: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'payments/send_reminder.html', context)

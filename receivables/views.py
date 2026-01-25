from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Case, When, Value, DecimalField, Count, Avg
from django.utils import timezone
from .models import (
    Payment, MpesaPayment, PaymentReceipt, PaymentReminder,
    PaymentAllocation, Receivable, Credit, BankStatementPattern, BankStatementUpload,
    UnmatchedTransaction
)
from .mpesa_service import MpesaService
from communications.services import CommunicationService
from core.models import Student, StudentFee, Term
import json
import uuid
from decimal import Decimal


# Helper functions for token resolution
def _get_payment_from_token_or_id(request, token_or_id):
    """Helper function to resolve payment from token or payment_id (backward compatibility)"""
    import uuid
    school = request.user.profile.school
    # Try to resolve as token first
    payment = Payment.from_signed_token(token_or_id)
    if payment and payment.school == school:
        return payment
    # Fallback to payment_id (UUID) for backward compatibility
    # Only try UUID if it's actually a valid UUID format
    try:
        # Validate it's a UUID before trying to use it
        uuid.UUID(str(token_or_id))
        # It's a valid UUID, try to find payment by payment_id
        return Payment.objects.get(payment_id=token_or_id, school=school)
    except (ValueError, TypeError):
        # Not a valid UUID, not a payment
        from django.http import Http404
        raise Http404("Payment not found")
    except Payment.DoesNotExist:
        from django.http import Http404
        raise Http404("Payment not found")

def _get_receivable_from_token_or_id(request, token_or_id):
    """Helper function to resolve receivable from token or id (backward compatibility)"""
    import uuid
    school = request.user.profile.school
    
    # Check if it's a UUID (likely a payment_id) - if so, it's not a receivable
    try:
        uuid.UUID(str(token_or_id))
        # It's a UUID, likely a payment_id, not a receivable
        from django.http import Http404
        raise Http404("Receivable not found")
    except (ValueError, TypeError):
        pass  # Not a UUID, continue checking
    
    receivable = Receivable.from_signed_token(token_or_id)
    if receivable and receivable.school == school:
        return receivable
    if str(token_or_id).isdigit():
        return get_object_or_404(Receivable, id=int(token_or_id), school=school)
    from django.http import Http404
    raise Http404("Receivable not found")

def _get_credit_from_token_or_id(request, token_or_id):
    """Helper function to resolve credit from token or id (backward compatibility)"""
    school = request.user.profile.school
    credit = Credit.from_signed_token(token_or_id)
    if credit and credit.school == school:
        return credit
    if str(token_or_id).isdigit():
        return get_object_or_404(Credit, id=int(token_or_id), school=school)
    from django.http import Http404
    raise Http404("Credit not found")

def _get_pattern_from_token_or_id(request, token_or_id):
    """Helper function to resolve bank statement pattern from token or id (backward compatibility)"""
    school = request.user.profile.school
    pattern = BankStatementPattern.from_signed_token(token_or_id)
    if pattern and pattern.school == school:
        return pattern
    if str(token_or_id).isdigit():
        return get_object_or_404(BankStatementPattern, id=int(token_or_id), school=school)
    from django.http import Http404
    raise Http404("Bank statement pattern not found")

def _get_unmatched_transaction_from_token_or_id(request, token_or_id):
    """Helper function to resolve unmatched transaction from token or id (backward compatibility)"""
    school = request.user.profile.school
    transaction = UnmatchedTransaction.from_signed_token(token_or_id)
    if transaction and transaction.school == school:
        return transaction
    if str(token_or_id).isdigit():
        return get_object_or_404(UnmatchedTransaction, id=int(token_or_id), school=school)
    from django.http import Http404
    raise Http404("Unmatched transaction not found")


@login_required
def payment_list(request):
    """List all payments"""
    from django.db.models import Prefetch
    school = request.user.profile.school
    payments = Payment.objects.filter(school=school).select_related(
        'student', 'student_fee__fee_category', 'student_fee__term'
    ).prefetch_related(
        Prefetch(
            'allocations',
            queryset=PaymentAllocation.objects.select_related(
                'student_fee__fee_category', 
                'student_fee__term'
            ).prefetch_related(
                'student_fee__receivables'
            )
        )
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
    
    return render(request, 'receivables/payment_list.html', context)


@login_required
def payment_detail(request, payment_id):
    """Payment detail view"""
    school = request.user.profile.school
    
    # Try to resolve from token first, then fall back to payment_id (UUID)
    try:
        payment = _get_payment_from_token_or_id(request, payment_id)
    except Http404:
        # If it's not a payment, raise 404
        raise Http404("Payment not found")
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'receivables/payment_detail.html', context)


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
            
            # Generate reference number in format: BUSINESS_NUMBER#STUDENT_ID
            mpesa_service = MpesaService()
            business_number = mpesa_service.business_shortcode
            reference = f"{business_number}#{student_fee.student.student_id}"
            
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
                return redirect('receivables:payment_detail', payment_id=result['payment_id'])
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
    
    return render(request, 'receivables/initiate_mpesa_payment.html', context)


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
            return redirect('receivables:payment_detail', payment_id=payment.get_signed_token())
            
        except ValueError:
            messages.error(request, 'Invalid amount.')
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'receivables/record_cash_payment.html', context)


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
            return redirect('receivables:payment_detail', payment_id=payment.get_signed_token())
            
        except ValueError:
            messages.error(request, 'Invalid amount.')
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    context = {
        'student_fee': student_fee,
        'student': student_fee.student,
    }
    
    return render(request, 'receivables/record_bank_payment.html', context)


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
    
    return render(request, 'receivables/receipt_list.html', context)


@login_required
def generate_receipt(request, payment_id):
    """Generate payment receipt"""
    school = request.user.profile.school
    payment = get_object_or_404(Payment, school=school, payment_id=payment_id)
    
    # Check if receipt already exists
    if hasattr(payment, 'receipt'):
        messages.info(request, 'Receipt already exists for this payment.')
        return redirect('receivables:payment_detail', payment_id=payment.payment_id)
    
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
        return redirect('receivables:payment_detail', payment_id=payment.payment_id)
        
    except Exception as e:
        messages.error(request, f'Error generating receipt: {str(e)}')
        return redirect('receivables:payment_detail', payment_id=payment.payment_id)


@login_required
def view_receipt(request, receipt_number):
    """View payment receipt"""
    school = request.user.profile.school
    receipt = get_object_or_404(PaymentReceipt, school=school, receipt_number=receipt_number)
    
    context = {
        'receipt': receipt,
    }
    
    return render(request, 'receivables/view_receipt.html', context)


@login_required
def fee_summary(request):
    """List students with total fees, amount paid, and balance per academic year/term"""
    school = request.user.profile.school
    
    # Filters
    year_filter = request.GET.get('year', '')
    term_filter = request.GET.get('term', '')
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    search_query = request.GET.get('search', '')
    grade_filter = request.GET.get('grade', '')
    
    fees = StudentFee.objects.filter(school=school).select_related('student', 'term', 'student__grade')
    
    # Filter by active status (default: show active only)
    if not show_inactive:
        fees = fees.filter(student__is_active=True)
    
    # Search functionality
    if search_query:
        fees = fees.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__parent_name__icontains=search_query) |
            Q(student__parent_phone__icontains=search_query)
        )
    
    # Filter by grade
    if grade_filter:
        fees = fees.filter(student__grade_id=grade_filter)
    
    if year_filter:
        fees = fees.filter(term__academic_year=year_filter)
    if term_filter:
        fees = fees.filter(term_id=term_filter)
    
    # Aggregate per student
    student_fees = fees.values(
        'student__id',
        'student__student_id',
        'student__first_name',
        'student__last_name',
        'student__grade__name',
        'student__is_active',
    ).annotate(
        total_charged=Sum('amount_charged'),
        total_paid=Sum('amount_paid'),
        balance=Sum(F('amount_charged') - F('amount_paid'), output_field=DecimalField()),
        unpaid=Sum(
            Case(
                When(amount_charged__gt=F('amount_paid'), then=F('amount_charged') - F('amount_paid')),
                default=Value(0, output_field=DecimalField())
            ),
            output_field=DecimalField()
        ),
        credit=Sum(
            Case(
                When(amount_paid__gt=F('amount_charged'), then=F('amount_paid') - F('amount_charged')),
                default=Value(0, output_field=DecimalField())
            ),
            output_field=DecimalField()
        ),
    ).order_by('-student__is_active', 'student__first_name', 'student__last_name')
    
    # Get detailed fees for each student
    student_ids = [item['student__id'] for item in student_fees]
    detailed_fees = {}
    for student_id in student_ids:
        student_detail_fees = fees.filter(student_id=student_id).select_related(
            'fee_category', 'term'
        ).order_by('-term__academic_year', '-term__term_number', 'fee_category__name')
        detailed_fees[student_id] = list(student_detail_fees)
    
    # Totals
    totals = fees.aggregate(
        total_charged=Sum('amount_charged', output_field=DecimalField()) or 0,
        total_paid=Sum('amount_paid', output_field=DecimalField()) or 0,
        total_unpaid=Sum(
            Case(
                When(amount_charged__gt=F('amount_paid'), then=F('amount_charged') - F('amount_paid')),
                default=Value(0, output_field=DecimalField())
            ),
            output_field=DecimalField()
        ) or 0,
        total_credit=Sum(
            Case(
                When(amount_paid__gt=F('amount_charged'), then=F('amount_paid') - F('amount_charged')),
                default=Value(0, output_field=DecimalField())
            ),
            output_field=DecimalField()
        ) or 0,
    )
    totals['balance'] = (totals['total_charged'] or 0) - (totals['total_paid'] or 0)
    
    # Filter options
    academic_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    if year_filter:
        terms = terms.filter(academic_year=year_filter)
    
    # Get grades for filter dropdown
    from core.models import Grade
    grades = Grade.objects.filter(school=school).order_by('name')
    
    context = {
        'student_fees': student_fees,
        'detailed_fees': detailed_fees,
        'totals': totals,
        'year_filter': year_filter,
        'term_filter': term_filter,
        'academic_years': academic_years,
        'terms': terms,
        'show_inactive': show_inactive,
        'search_query': search_query,
        'grade_filter': grade_filter,
        'grades': grades,
    }
    
    return render(request, 'receivables/fee_summary.html', context)


@login_required
def fee_report(request):
    """Comprehensive fee management report - printable"""
    school = request.user.profile.school
    
    # Filters
    year_filter = request.GET.get('year', '')
    term_filter = request.GET.get('term', '')
    grade_filter = request.GET.get('grade', '')
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    
    fees = StudentFee.objects.filter(school=school).select_related('student', 'term', 'student__grade', 'fee_category')
    
    # Filter by active status
    if not show_inactive:
        fees = fees.filter(student__is_active=True)
    
    # Filter by grade
    if grade_filter:
        fees = fees.filter(student__grade_id=grade_filter)
    
    # Filter by year and term
    if year_filter:
        fees = fees.filter(term__academic_year=year_filter)
    if term_filter:
        fees = fees.filter(term_id=term_filter)
    
    # Overall statistics
    total_students = fees.values('student').distinct().count()
    total_fees_charged = fees.aggregate(total=Sum('amount_charged', output_field=DecimalField()))['total'] or 0
    total_fees_paid = fees.aggregate(total=Sum('amount_paid', output_field=DecimalField()))['total'] or 0
    total_balance = total_fees_charged - total_fees_paid
    
    # Overdue statistics
    overdue_fees = fees.filter(
        is_paid=False,
        due_date__lt=timezone.now().date()
    )
    overdue_count = overdue_fees.count()
    overdue_amount = overdue_fees.aggregate(total=Sum('amount_charged', output_field=DecimalField()))['total'] or 0
    
    # Payment statistics
    paid_fees = fees.filter(is_paid=True)
    paid_count = paid_fees.count()
    paid_amount = paid_fees.aggregate(total=Sum('amount_paid', output_field=DecimalField()))['total'] or 0
    
    # Pending statistics
    pending_fees = fees.filter(is_paid=False, due_date__gte=timezone.now().date())
    pending_count = pending_fees.count()
    pending_amount = pending_fees.aggregate(total=Sum('amount_charged', output_field=DecimalField()))['total'] or 0
    
    # Fee breakdown by category
    from core.models import FeeCategory
    category_breakdown = []
    for item in fees.values('fee_category__name').annotate(
        total_charged=Sum('amount_charged', output_field=DecimalField()),
        total_paid=Sum('amount_paid', output_field=DecimalField()),
        count=Count('id')
    ).order_by('-total_charged'):
        item['balance'] = float(item['total_charged'] or 0) - float(item['total_paid'] or 0)
        category_breakdown.append(item)
    
    # Fee breakdown by term
    term_breakdown = []
    for item in fees.values('term__name', 'term__academic_year').annotate(
        total_charged=Sum('amount_charged', output_field=DecimalField()),
        total_paid=Sum('amount_paid', output_field=DecimalField()),
        count=Count('id')
    ).order_by('-term__academic_year', '-term__term_number'):
        item['balance'] = float(item['total_charged'] or 0) - float(item['total_paid'] or 0)
        term_breakdown.append(item)
    
    # Fee breakdown by grade
    grade_breakdown = []
    for item in fees.values('student__grade__name').annotate(
        total_charged=Sum('amount_charged', output_field=DecimalField()),
        total_paid=Sum('amount_paid', output_field=DecimalField()),
        student_count=Count('student', distinct=True),
        fee_count=Count('id')
    ).order_by('student__grade__name'):
        item['balance'] = float(item['total_charged'] or 0) - float(item['total_paid'] or 0)
        grade_breakdown.append(item)
    
    # Top students by balance
    top_balances = fees.values(
        'student__id',
        'student__student_id',
        'student__first_name',
        'student__last_name',
        'student__grade__name'
    ).annotate(
        total_balance=Sum(F('amount_charged') - F('amount_paid'), output_field=DecimalField())
    ).filter(total_balance__gt=0).order_by('-total_balance')[:10]
    
    # Recent payments (last 30 days)
    from datetime import timedelta
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    from .models import Payment
    recent_payments = Payment.objects.filter(
        school=school,
        payment_date__date__gte=thirty_days_ago,
        status='completed'
    ).select_related('student').order_by('-payment_date')[:10]
    
    # Filter options
    from core.models import Grade, Term
    academic_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    if year_filter:
        terms = terms.filter(academic_year=year_filter)
    grades = Grade.objects.filter(school=school).order_by('name')
    
    # Get selected filters for display
    selected_term = None
    if term_filter:
        selected_term = Term.objects.filter(id=term_filter).first()
    selected_grade = None
    if grade_filter:
        selected_grade = Grade.objects.filter(id=grade_filter).first()
    
    context = {
        'school': school,
        'total_students': total_students,
        'total_fees_charged': float(total_fees_charged),
        'total_fees_paid': float(total_fees_paid),
        'total_balance': float(total_balance),
        'overdue_count': overdue_count,
        'overdue_amount': float(overdue_amount),
        'paid_count': paid_count,
        'paid_amount': float(paid_amount),
        'pending_count': pending_count,
        'pending_amount': float(pending_amount),
        'category_breakdown': category_breakdown,
        'term_breakdown': term_breakdown,
        'grade_breakdown': grade_breakdown,
        'top_balances': top_balances,
        'recent_payments': recent_payments,
        'year_filter': year_filter,
        'term_filter': term_filter,
        'grade_filter': grade_filter,
        'selected_term': selected_term,
        'selected_grade': selected_grade,
        'academic_years': academic_years,
        'terms': terms,
        'grades': grades,
        'show_inactive': show_inactive,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'receivables/fee_report.html', context)


@login_required
def financial_reports(request):
    """Financial reports dashboard"""
    school = request.user.profile.school
    return render(request, 'receivables/financial_reports.html', {'school': school})


@login_required
def payment_collection_report(request):
    """Payment collection report - daily/weekly/monthly"""
    school = request.user.profile.school
    
    # Filters
    period = request.GET.get('period', 'monthly')  # daily, weekly, monthly
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    payments = Payment.objects.filter(
        school=school,
        status='completed'
    ).select_related('student', 'student_fee__fee_category', 'student_fee__term')
    
    # Date filtering
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    
    # Group by period
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
    collection_data = []
    
    if period == 'daily':
        grouped = payments.annotate(
            period=TruncDate('payment_date')
        ).values('period').annotate(
            total_amount=Sum('amount', output_field=DecimalField()),
            count=Count('id')
        ).order_by('-period')
        
        for item in grouped:
            collection_data.append({
                'period': item['period'].strftime('%d %b %Y') if item['period'] else 'Unknown',
                'total_amount': float(item['total_amount'] or 0),
                'count': item['count'],
            })
    elif period == 'weekly':
        grouped = payments.annotate(
            period=TruncWeek('payment_date')
        ).values('period').annotate(
            total_amount=Sum('amount', output_field=DecimalField()),
            count=Count('id')
        ).order_by('-period')
        
        for item in grouped:
            collection_data.append({
                'period': f"Week of {item['period'].strftime('%d %b %Y')}" if item['period'] else 'Unknown',
                'total_amount': float(item['total_amount'] or 0),
                'count': item['count'],
            })
    else:  # monthly
        grouped = payments.annotate(
            period=TruncMonth('payment_date')
        ).values('period').annotate(
            total_amount=Sum('amount', output_field=DecimalField()),
            count=Count('id')
        ).order_by('-period')
        
        for item in grouped:
            collection_data.append({
                'period': item['period'].strftime('%B %Y') if item['period'] else 'Unknown',
                'total_amount': float(item['total_amount'] or 0),
                'count': item['count'],
            })
    
    # Overall statistics
    total_collected = payments.aggregate(total=Sum('amount', output_field=DecimalField()))['total'] or 0
    total_count = payments.count()
    avg_payment = total_collected / total_count if total_count > 0 else 0
    
    context = {
        'school': school,
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'collection_data': collection_data,
        'total_collected': float(total_collected),
        'total_count': total_count,
        'avg_payment': float(avg_payment),
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'receivables/payment_collection_report.html', context)


@login_required
def outstanding_fees_report(request):
    """Detailed outstanding fees report"""
    school = request.user.profile.school
    
    # Filters
    grade_filter = request.GET.get('grade', '')
    term_filter = request.GET.get('term', '')
    overdue_only = request.GET.get('overdue_only', 'false').lower() == 'true'
    
    fees = StudentFee.objects.filter(
        school=school,
        student__is_active=True
    ).select_related('student', 'term', 'fee_category', 'student__grade')
    
    # Filter by grade
    if grade_filter:
        fees = fees.filter(student__grade_id=grade_filter)
    
    # Filter by term
    if term_filter:
        fees = fees.filter(term_id=term_filter)
    
    # Get outstanding fees (balance > 0)
    # Use 'calculated_balance' to avoid conflict with the 'balance' property
    outstanding_fees = fees.annotate(
        calculated_balance=F('amount_charged') - F('amount_paid')
    ).filter(calculated_balance__gt=0)
    
    # Filter overdue only
    if overdue_only:
        outstanding_fees = outstanding_fees.filter(
            due_date__lt=timezone.now().date(),
            is_paid=False
        )
    
    outstanding_fees = outstanding_fees.order_by('-calculated_balance', 'due_date')
    
    # Statistics
    total_outstanding = outstanding_fees.aggregate(
        total=Sum('calculated_balance', output_field=DecimalField())
    )['total'] or 0
    
    overdue_count = outstanding_fees.filter(
        due_date__lt=timezone.now().date()
    ).count()
    
    overdue_amount = outstanding_fees.filter(
        due_date__lt=timezone.now().date()
    ).aggregate(
        total=Sum('calculated_balance', output_field=DecimalField())
    )['total'] or 0
    
    # Group by grade
    from core.models import Grade
    grade_breakdown = outstanding_fees.values('student__grade__name').annotate(
        total_outstanding=Sum('calculated_balance', output_field=DecimalField()),
        count=Count('id'),
        student_count=Count('student', distinct=True)
    ).order_by('student__grade__name')
    
    # Filter options
    grades = Grade.objects.filter(school=school).order_by('name')
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    
    selected_grade = None
    if grade_filter:
        selected_grade = Grade.objects.filter(id=grade_filter).first()
    selected_term = None
    if term_filter:
        selected_term = Term.objects.filter(id=term_filter).first()
    
    context = {
        'school': school,
        'outstanding_fees': outstanding_fees,
        'total_outstanding': float(total_outstanding),
        'overdue_count': overdue_count,
        'overdue_amount': float(overdue_amount),
        'grade_breakdown': grade_breakdown,
        'grade_filter': grade_filter,
        'term_filter': term_filter,
        'selected_grade': selected_grade,
        'selected_term': selected_term,
        'grades': grades,
        'terms': terms,
        'overdue_only': overdue_only,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'receivables/outstanding_fees_report.html', context)


@login_required
def collection_summary_report(request):
    """Fee collection summary with trends"""
    school = request.user.profile.school
    
    # Filters
    year_filter = request.GET.get('year', '')
    term_filter = request.GET.get('term', '')
    
    fees = StudentFee.objects.filter(school=school).select_related('term', 'student__grade')
    payments = Payment.objects.filter(school=school, status='completed').select_related('student')
    
    # Filter by year
    if year_filter:
        fees = fees.filter(term__academic_year=year_filter)
        payments = payments.filter(payment_date__year=year_filter)
    
    # Filter by term
    if term_filter:
        fees = fees.filter(term_id=term_filter)
        term = Term.objects.filter(id=term_filter).first()
        if term:
            payments = payments.filter(
                payment_date__date__gte=term.start_date,
                payment_date__date__lte=term.end_date
            )
    
    # Monthly collection trends (last 12 months)
    from datetime import timedelta
    from django.db.models.functions import TruncMonth
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365)
    
    monthly_collections = payments.filter(
        payment_date__date__gte=start_date,
        payment_date__date__lte=end_date
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total_collected=Sum('amount', output_field=DecimalField()),
        count=Count('id')
    ).order_by('month')
    
    monthly_data = []
    for item in monthly_collections:
        monthly_data.append({
            'month': item['month'].strftime('%b %Y') if item['month'] else 'Unknown',
            'total_collected': float(item['total_collected'] or 0),
            'count': item['count'],
        })
    
    # Collection by term
    term_collections = fees.values('term__name', 'term__academic_year').annotate(
        total_charged=Sum('amount_charged', output_field=DecimalField()),
        total_paid=Sum('amount_paid', output_field=DecimalField()),
    ).order_by('-term__academic_year', '-term__term_number')
    
    term_data = []
    for item in term_collections:
        total_charged = float(item['total_charged'] or 0)
        total_paid = float(item['total_paid'] or 0)
        outstanding = total_charged - total_paid
        collection_rate = (total_paid / total_charged * 100) if total_charged > 0 else 0
        term_data.append({
            'term': item['term__name'],
            'academic_year': item['term__academic_year'],
            'total_charged': total_charged,
            'total_paid': total_paid,
            'outstanding': outstanding,
            'collection_rate': collection_rate,
        })
    
    # Overall statistics
    total_charged = fees.aggregate(total=Sum('amount_charged', output_field=DecimalField()))['total'] or 0
    total_paid = fees.aggregate(total=Sum('amount_paid', output_field=DecimalField()))['total'] or 0
    total_outstanding = float(total_charged) - float(total_paid)
    overall_collection_rate = (total_paid / total_charged * 100) if total_charged > 0 else 0
    
    # Filter options
    academic_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    terms = Term.objects.filter(school=school).order_by('-academic_year', 'term_number')
    if year_filter:
        terms = terms.filter(academic_year=year_filter)
    
    context = {
        'school': school,
        'year_filter': year_filter,
        'term_filter': term_filter,
        'monthly_data': json.dumps(monthly_data),
        'term_data': term_data,
        'total_charged': float(total_charged),
        'total_paid': float(total_paid),
        'total_outstanding': total_outstanding,
        'overall_collection_rate': overall_collection_rate,
        'academic_years': academic_years,
        'terms': terms,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'receivables/collection_summary_report.html', context)


@login_required
def payment_method_analysis(request):
    """Payment method analysis report"""
    school = request.user.profile.school
    
    # Filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    year_filter = request.GET.get('year', '')
    
    payments = Payment.objects.filter(
        school=school,
        status='completed'
    ).select_related('student')
    
    # Date filtering
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    if year_filter:
        payments = payments.filter(payment_date__year=year_filter)
    
    # Breakdown by payment method
    method_breakdown = payments.values('payment_method').annotate(
        total_amount=Sum('amount', output_field=DecimalField()),
        count=Count('id'),
        avg_amount=Avg('amount')
    ).order_by('-total_amount')
    
    method_data = []
    total_all = payments.aggregate(total=Sum('amount', output_field=DecimalField()))['total'] or 0
    
    for item in method_breakdown:
        total = float(item['total_amount'] or 0)
        percentage = (total / float(total_all) * 100) if total_all > 0 else 0
        method_data.append({
            'method': dict(Payment.PAYMENT_METHOD_CHOICES).get(item['payment_method'], item['payment_method']),
            'total_amount': total,
            'count': item['count'],
            'avg_amount': float(item['avg_amount'] or 0),
            'percentage': percentage,
        })
    
    # Monthly trend by method (last 6 months)
    from datetime import timedelta
    from django.db.models.functions import TruncMonth
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=180)
    
    monthly_by_method = payments.filter(
        payment_date__date__gte=start_date,
        payment_date__date__lte=end_date
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month', 'payment_method').annotate(
        total_amount=Sum('amount', output_field=DecimalField())
    ).order_by('month', 'payment_method')
    
    # Organize monthly data by method
    monthly_method_data = {}
    for item in monthly_by_method:
        method = dict(Payment.PAYMENT_METHOD_CHOICES).get(item['payment_method'], item['payment_method'])
        month = item['month'].strftime('%b %Y') if item['month'] else 'Unknown'
        
        if method not in monthly_method_data:
            monthly_method_data[method] = []
        monthly_method_data[method].append({
            'month': month,
            'amount': float(item['total_amount'] or 0),
        })
    
    # Overall statistics
    total_payments = payments.count()
    total_amount = float(total_all)
    avg_payment = total_amount / total_payments if total_payments > 0 else 0
    
    # Filter options
    academic_years = Term.objects.filter(school=school).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    context = {
        'school': school,
        'method_data': method_data,
        'monthly_method_data': json.dumps(monthly_method_data),
        'method_data_json': json.dumps(method_data),
        'total_payments': total_payments,
        'total_amount': total_amount,
        'avg_payment': avg_payment,
        'date_from': date_from,
        'date_to': date_to,
        'year_filter': year_filter,
        'academic_years': academic_years,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'receivables/payment_method_analysis.html', context)


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
    
    return render(request, 'receivables/reminder_list.html', context)


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
    
    return render(request, 'receivables/send_reminder.html', context)


# ==================== Receivables Views ====================

@login_required
def receivable_list(request):
    """List all receivables with search and allocation viewing"""
    from core.decorators import permission_required
    from django.db.models import Prefetch, F, Case, When, Value, DecimalField
    from django.db import ProgrammingError
    
    school = request.user.profile.school
    
    # Get all StudentFee records with outstanding balances
    # This ensures we show all fees that match the dashboard calculation
    # First, ensure all StudentFee records have corresponding Receivable records
    # Note: StudentFee has a balance property, so we filter using F() expressions
    # Filter: amount_charged > amount_paid (which means balance > 0)
    student_fees_with_balance = StudentFee.objects.filter(
        school=school
    ).filter(
        amount_charged__gt=F('amount_paid')
    )
    
    # Sync receivables for any StudentFee that doesn't have one or update existing ones
    try:
        for student_fee in student_fees_with_balance:
            receivable, created = Receivable.objects.get_or_create(
                school=student_fee.school,
                student_fee=student_fee,
                defaults={
                    'student': student_fee.student,
                    'amount_due': student_fee.amount_charged,
                    'amount_paid': student_fee.amount_paid,
                    'due_date': student_fee.due_date,
                    'is_cleared': student_fee.is_paid,
                }
            )
            if not created:
                # Update existing receivable to match StudentFee
                receivable.amount_due = student_fee.amount_charged
                receivable.amount_paid = student_fee.amount_paid
                receivable.due_date = student_fee.due_date
                receivable.is_cleared = student_fee.is_paid
                if student_fee.is_paid and not receivable.cleared_at:
                    from django.utils import timezone
                    receivable.cleared_at = timezone.now()
                elif not student_fee.is_paid:
                    receivable.cleared_at = None
                receivable.save()
    except ProgrammingError as e:
        # Receivable table doesn't exist - migrations not run
        if 'receivables_receivable' in str(e) or 'does not exist' in str(e):
            messages.error(
                request, 
                'Database migration required: The Receivables table does not exist. '
                'Please run migrations in production: python manage.py migrate receivables'
            )
            # Return empty context to avoid further errors
            return render(request, 'receivables/receivable_list.html', {
                'page_obj': None,
                'search_query': '',
                'total_due': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'total_outstanding': Decimal('0.00'),
            })
        else:
            raise  # Re-raise if it's a different ProgrammingError
    
    # Now query Receivable records (which should now exist for all outstanding fees)
    try:
        receivables = Receivable.objects.filter(
            school=school,
            is_cleared=False
        ).select_related(
            'student', 'student_fee__fee_category', 'student_fee__term'
        ).prefetch_related(
            Prefetch(
                'student_fee__payment_allocations',
                queryset=PaymentAllocation.objects.select_related('payment', 'payment__student')
            )
        ).order_by('due_date', 'student__student_id')
    except ProgrammingError as e:
        # Receivable table doesn't exist - migrations not run
        if 'receivables_receivable' in str(e) or 'does not exist' in str(e):
            messages.error(
                request, 
                'Database migration required: The Receivables table does not exist. '
                'Please run migrations in production: python manage.py migrate receivables'
            )
            # Return empty context to avoid further errors
            return render(request, 'receivables/receivable_list.html', {
                'page_obj': None,
                'search_query': '',
                'total_due': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'total_outstanding': Decimal('0.00'),
            })
        else:
            raise  # Re-raise if it's a different ProgrammingError
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        receivables = receivables.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student_fee__fee_category__name__icontains=search_query)
        )
    
    # Filter by status
    # Note: Receivable has a balance property, so we filter using F() expressions on fields directly
    status_filter = request.GET.get('status', '')
    if status_filter == 'outstanding':
        # Already filtered by is_cleared=False, but ensure amount_due > amount_paid
        receivables = receivables.filter(
            amount_due__gt=F('amount_paid')
        )
    elif status_filter == 'overdue':
        from django.utils import timezone
        receivables = receivables.filter(
            due_date__lt=timezone.now().date(),
            amount_due__gt=F('amount_paid')
        )
    elif status_filter == 'cleared':
        receivables = Receivable.objects.filter(
            school=school,
            is_cleared=True
        ).select_related(
            'student', 'student_fee__fee_category', 'student_fee__term'
        ).prefetch_related(
            Prefetch(
                'student_fee__payment_allocations',
                queryset=PaymentAllocation.objects.select_related('payment', 'payment__student')
            )
        ).order_by('-cleared_at', 'student__student_id')
    
    # Calculate totals - use the filtered queryset
    # For outstanding balance, calculate using F() expression with different annotation name
    total_due = receivables.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    total_paid = receivables.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    # For outstanding, calculate difference using annotation with different name to avoid conflict
    if status_filter != 'cleared':
        # Use outstanding_amt to avoid conflict with balance property
        receivables_with_outstanding = receivables.annotate(
            outstanding_amt=F('amount_due') - F('amount_paid')
        ).filter(outstanding_amt__gt=0)
        total_outstanding = receivables_with_outstanding.aggregate(
            total=Sum('outstanding_amt')
        )['total'] or Decimal('0.00')
    else:
        total_outstanding = Decimal('0.00')
    
    # Pagination
    paginator = Paginator(receivables, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_due': total_due,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
    }
    
    return render(request, 'receivables/receivable_list.html', context)


@login_required
def receivable_detail(request, receivable_id):
    """View receivable details and allocations"""
    school = request.user.profile.school
    import uuid
    
    # First check if this is actually a payment UUID or token (since receivable_detail comes first in URLs)
    # If it is, directly render payment detail to avoid redirect loop
    payment = None
    
    # Try as signed token first
    payment = Payment.from_signed_token(receivable_id)
    
    # If not a token, try as UUID (payment_id)
    if not payment:
        try:
            payment_uuid = uuid.UUID(str(receivable_id))
            payment = Payment.objects.filter(school=school, payment_id=payment_uuid).first()
        except (ValueError, TypeError):
            pass  # Not a valid UUID
    
    if payment and payment.school == school:
        # This is actually a payment, render payment detail directly
        context = {
            'payment': payment,
        }
        return render(request, 'receivables/payment_detail.html', context)
    
    # Try to resolve as receivable
    receivable = _get_receivable_from_token_or_id(request, receivable_id)
    school = receivable.school
    
    # Get all payment allocations for this receivable's student_fee
    allocations = PaymentAllocation.objects.filter(
        school=school,
        student_fee=receivable.student_fee
    ).select_related('payment', 'payment__student', 'created_by').order_by('-created_at')
    
    context = {
        'receivable': receivable,
        'allocations': allocations,
    }
    
    return render(request, 'receivables/receivable_detail.html', context)


# ==================== Credits Views ====================

@login_required
def credit_list(request):
    """List all credits"""
    school = request.user.profile.school
    credits = Credit.objects.filter(school=school).select_related(
        'student', 'payment', 'applied_to_fee', 'created_by'
    ).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        credits = credits.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Filter by applied status
    applied_filter = request.GET.get('applied', '')
    if applied_filter == 'yes':
        credits = credits.filter(is_applied=True)
    elif applied_filter == 'no':
        credits = credits.filter(is_applied=False)
    
    # Filter by source
    source_filter = request.GET.get('source', '')
    if source_filter:
        credits = credits.filter(source=source_filter)
    
    # Check for outstanding receivables for all available credits (for apply all button state)
    from core.models import StudentFee
    from django.db.models import F
    available_credits_all = credits.filter(is_applied=False)
    has_any_outstanding = False
    if available_credits_all.exists():
        # Check if any available credit has outstanding receivables
        for credit in available_credits_all:
            outstanding_fees = StudentFee.objects.filter(
                school=school,
                student=credit.student,
                amount_charged__gt=F('amount_paid')
            ).exists()
            if outstanding_fees:
                has_any_outstanding = True
                break  # Found at least one, no need to check further
    
    # Pagination
    paginator = Paginator(credits, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Check for outstanding receivables for each credit on current page (for individual apply button state)
    credit_outstanding_info = {}
    for credit in page_obj:
        if not credit.is_applied:
            # Check if student has outstanding fees
            outstanding_fees = StudentFee.objects.filter(
                school=school,
                student=credit.student,
                amount_charged__gt=F('amount_paid')
            ).exists()
            credit_outstanding_info[credit.id] = outstanding_fees
    
    # Calculate totals
    total_credits = credits.aggregate(total=Sum('amount'))['total'] or 0
    applied_credits = credits.filter(is_applied=True).aggregate(total=Sum('amount'))['total'] or 0
    available_credits = total_credits - applied_credits
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'applied_filter': applied_filter,
        'source_filter': source_filter,
        'total_credits': total_credits,
        'applied_credits': applied_credits,
        'available_credits': available_credits,
        'credit_outstanding_info': credit_outstanding_info,
        'has_any_outstanding': has_any_outstanding,
    }
    
    return render(request, 'receivables/credit_list.html', context)


@login_required
def credit_create(request):
    """Create a new credit"""
    from .forms import CreditForm
    
    school = request.user.profile.school
    
    if request.method == 'POST':
        form = CreditForm(request.POST, school=school)
        if form.is_valid():
            credit = form.save(commit=False)
            credit.school = school
            credit.created_by = request.user
            credit.save()
            messages.success(request, f'Credit of KES {credit.amount} created for {credit.student.full_name}.')
            return redirect('receivables:credit_list')
    else:
        form = CreditForm(school=school)
    
    return render(request, 'receivables/credit_form.html', {
        'form': form,
        'title': 'Create Credit'
    })


@login_required
def credit_edit(request, credit_id):
    """Edit an existing credit"""
    from .forms import CreditForm
    
    credit = _get_credit_from_token_or_id(request, credit_id)
    school = credit.school
    
    # Prevent editing applied credits
    if credit.is_applied:
        messages.error(request, 'Cannot edit a credit that has already been applied.')
        return redirect('receivables:credit_list')
    
    if request.method == 'POST':
        form = CreditForm(request.POST, instance=credit, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, 'Credit updated successfully.')
            return redirect('receivables:credit_list')
    else:
        form = CreditForm(instance=credit, school=school)
    
    return render(request, 'receivables/credit_form.html', {
        'form': form,
        'title': 'Edit Credit',
        'credit': credit
    })


@login_required
def credit_apply(request, credit_id):
    """Apply a credit to outstanding receivables (can apply to multiple fees)"""
    from django.db import transaction as db_transaction
    from django.db.models import F
    from core.models import StudentFee
    
    credit = _get_credit_from_token_or_id(request, credit_id)
    school = credit.school
    
    # Prevent applying already applied credits
    if credit.is_applied:
        messages.error(request, 'This credit has already been applied.')
        return redirect('receivables:credit_list')
    
    if request.method == 'POST':
        student_fee_id = request.POST.get('student_fee_id')
        
        try:
            with db_transaction.atomic():
                if student_fee_id:
                    # Apply to specific fee only
                    student_fee = StudentFee.objects.get(
                        id=student_fee_id,
                        school=school,
                        student=credit.student,
                        amount_charged__gt=F('amount_paid')
                    )
                    
                    outstanding = student_fee.amount_charged - student_fee.amount_paid
                    amount_to_apply = min(float(credit.amount), float(outstanding))
                    
                    # Update student fee
                    student_fee.amount_paid += Decimal(str(amount_to_apply))
                    if student_fee.amount_paid >= student_fee.amount_charged:
                        student_fee.is_paid = True
                    student_fee.save()
                    
                    # Mark credit as applied
                    credit.is_applied = True
                    credit.applied_to_fee = student_fee
                    from django.utils import timezone
                    credit.applied_at = timezone.now()
                    credit.save()
                    
                    # Create new credit for remaining amount if any
                    if amount_to_apply < float(credit.amount):
                        remaining = float(credit.amount) - amount_to_apply
                        new_credit = Credit.objects.create(
                            school=school,
                            student=credit.student,
                            amount=Decimal(str(remaining)),
                            source=credit.source,
                            payment=credit.payment,
                            description=f'Remaining credit from application of credit ID {credit.id} to {student_fee.fee_category.name}. Original credit amount: {credit.amount}, Applied: {amount_to_apply:.2f}, Remaining: {remaining:.2f}',
                            created_by=request.user
                        )
                        messages.success(request, f'Credit of KES {amount_to_apply:.2f} applied to {student_fee.fee_category.name}. Remaining KES {remaining:.2f} has been created as a new credit (ID: {new_credit.id}) for future application.')
                    else:
                        messages.success(request, f'Credit of KES {amount_to_apply:.2f} applied to {student_fee.fee_category.name}.')
                else:
                    # Apply to multiple outstanding fees (oldest first)
                    outstanding_fees = StudentFee.objects.filter(
                        school=school,
                        student=credit.student,
                        amount_charged__gt=F('amount_paid')
                    ).order_by('due_date', 'created_at')
                    
                    if not outstanding_fees.exists():
                        messages.error(request, 'No outstanding receivables found for this student.')
                        return redirect('receivables:credit_list')
                    
                    # Apply credit across multiple fees
                    remaining_credit = float(credit.amount)
                    applied_fees = []
                    
                    for student_fee in outstanding_fees:
                        if remaining_credit <= 0.01:  # Less than 1 cent remaining
                            break
                        
                        outstanding = float(student_fee.amount_charged - student_fee.amount_paid)
                        if outstanding <= 0:
                            continue
                        
                        # Apply what we can to this fee
                        amount_to_apply = min(remaining_credit, outstanding)
                        
                        # Update student fee
                        student_fee.amount_paid += Decimal(str(amount_to_apply))
                        if student_fee.amount_paid >= student_fee.amount_charged:
                            student_fee.is_paid = True
                        student_fee.save()
                        
                        applied_fees.append({
                            'fee': student_fee,
                            'amount': amount_to_apply
                        })
                        remaining_credit -= amount_to_apply
                    
                    if applied_fees:
                        # Mark credit as applied (use first fee as primary reference)
                        credit.is_applied = True
                        credit.applied_to_fee = applied_fees[0]['fee']
                        from django.utils import timezone
                        credit.applied_at = timezone.now()
                        credit.save()
                        
                        # Build success message
                        fee_names = [f"{fee['fee'].fee_category.name} (KES {fee['amount']:.2f})" for fee in applied_fees]
                        if len(applied_fees) == 1:
                            messages.success(request, f'Credit of KES {applied_fees[0]["amount"]:.2f} applied to {fee_names[0]}.')
                        else:
                            total_applied = sum(f['amount'] for f in applied_fees)
                            messages.success(request, f'Credit of KES {total_applied:.2f} applied to {len(applied_fees)} fee(s): {", ".join(fee_names)}.')
                        
                        # Create new credit for remaining amount if any
                        if remaining_credit > 0.01:
                            new_credit = Credit.objects.create(
                                school=school,
                                student=credit.student,
                                amount=Decimal(str(remaining_credit)),
                                source=credit.source,
                                payment=credit.payment,
                                description=f'Remaining credit from application of credit ID {credit.id}. Original credit amount: {credit.amount}, Applied: {sum(f["amount"] for f in applied_fees):.2f}, Remaining: {remaining_credit:.2f}',
                                created_by=request.user
                            )
                            messages.info(request, f'Remaining credit of KES {remaining_credit:.2f} has been created as a new credit (ID: {new_credit.id}) for future application.')
                    else:
                        messages.error(request, 'Could not apply credit to any fees.')
                
        except StudentFee.DoesNotExist:
            messages.error(request, 'Selected fee not found or already paid.')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error applying credit: {str(e)}', exc_info=True)
            messages.error(request, f'Error applying credit: {str(e)}')
    
    return redirect('receivables:credit_list')


@login_required
def credit_apply_all(request):
    """Apply all available credits to outstanding receivables"""
    from django.db import transaction as db_transaction
    from django.db.models import F
    from core.models import StudentFee
    
    school = request.user.profile.school
    
    if request.method == 'POST':
        # Get all available (unapplied) credits
        available_credits = Credit.objects.filter(
            school=school,
            is_applied=False
        ).select_related('student')
        
        if not available_credits.exists():
            messages.info(request, 'No available credits to apply.')
            return redirect('receivables:credit_list')
        
        applied_count = 0
        skipped_count = 0
        total_applied_amount = Decimal('0.00')
        
        try:
            with db_transaction.atomic():
                for credit in available_credits:
                    # Get outstanding fees for this student
                    outstanding_fees = StudentFee.objects.filter(
                        school=school,
                        student=credit.student,
                        amount_charged__gt=F('amount_paid')
                    ).order_by('due_date', 'created_at')
                    
                    if not outstanding_fees.exists():
                        skipped_count += 1
                        continue
                    
                    # Apply credit across multiple fees
                    remaining_credit = float(credit.amount)
                    applied_fees = []
                    
                    for student_fee in outstanding_fees:
                        if remaining_credit <= 0.01:  # Less than 1 cent remaining
                            break
                        
                        outstanding = float(student_fee.amount_charged - student_fee.amount_paid)
                        if outstanding <= 0:
                            continue
                        
                        # Apply what we can to this fee
                        amount_to_apply = min(remaining_credit, outstanding)
                        
                        # Update student fee
                        student_fee.amount_paid += Decimal(str(amount_to_apply))
                        if student_fee.amount_paid >= student_fee.amount_charged:
                            student_fee.is_paid = True
                        student_fee.save()
                        
                        applied_fees.append({
                            'fee': student_fee,
                            'amount': amount_to_apply
                        })
                        remaining_credit -= amount_to_apply
                    
                    if applied_fees:
                        # Mark credit as applied (use first fee as primary reference)
                        credit.is_applied = True
                        credit.applied_to_fee = applied_fees[0]['fee']
                        from django.utils import timezone
                        credit.applied_at = timezone.now()
                        credit.save()
                        
                        total_applied = sum(f['amount'] for f in applied_fees)
                        total_applied_amount += Decimal(str(total_applied))
                        applied_count += 1
                        
                        # Create new credit for remaining amount if any
                        if remaining_credit > 0.01:
                            Credit.objects.create(
                                school=school,
                                student=credit.student,
                                amount=Decimal(str(remaining_credit)),
                                source=credit.source,
                                payment=credit.payment,
                                description=f'Remaining credit from bulk application of credit ID {credit.id}. Original credit amount: {credit.amount}, Applied: {total_applied:.2f}, Remaining: {remaining_credit:.2f}',
                                created_by=request.user
                            )
                    else:
                        skipped_count += 1
            
            # Build success message
            if applied_count > 0:
                messages.success(request, f'Applied {applied_count} credit(s) totaling KES {total_applied_amount:.2f} to outstanding receivables.')
            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} credit(s) with no outstanding receivables.')
            if applied_count == 0 and skipped_count > 0:
                messages.warning(request, 'No credits could be applied. No outstanding receivables found for any credits.')
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error applying all credits: {str(e)}', exc_info=True)
            messages.error(request, f'Error applying credits: {str(e)}')
    
    return redirect('receivables:credit_list')


@login_required
def credit_delete(request, credit_id):
    """Delete a credit"""
    credit = _get_credit_from_token_or_id(request, credit_id)
    
    # Prevent deleting applied credits
    if credit.is_applied:
        messages.error(request, 'Cannot delete a credit that has already been applied.')
        return redirect('receivables:credit_list')
    
    if request.method == 'POST':
        student_name = credit.student.full_name
        amount = credit.amount
        credit.delete()
        messages.success(request, f'Credit of KES {amount} for {student_name} deleted successfully.')
        return redirect('receivables:credit_list')
    
    return render(request, 'receivables/credit_confirm_delete.html', {'credit': credit})


# ==================== Bank Statement Pattern Views ====================

@login_required
def bank_statement_pattern_list(request):
    """List all bank statement patterns for the school"""
    from core.models import School
    
    # Allow superadmins to view patterns for a specific school via query parameter
    school_token = request.GET.get('school', '')
    if school_token and (request.user.is_superuser or request.user.profile.roles.filter(name='super_admin').exists()):
        school = School.from_signed_token(school_token)
        if not school:
            school = request.user.profile.school
    else:
        school = request.user.profile.school
    
    patterns = BankStatementPattern.objects.filter(school=school).order_by('bank_name', 'pattern_name')
    
    context = {
        'patterns': patterns,
        'school': school,
    }
    
    return render(request, 'receivables/bank_statement_pattern_list.html', context)


@login_required
def bank_statement_pattern_create(request):
    """Create a new bank statement pattern"""
    from receivables.forms import BankStatementPatternForm
    from core.models import School
    
    # Allow superadmins to create patterns for a specific school via query parameter
    school_token = request.GET.get('school', '')
    if school_token and (request.user.is_superuser or request.user.profile.roles.filter(name='super_admin').exists()):
        school = School.from_signed_token(school_token)
        if not school:
            school = request.user.profile.school
    else:
        school = request.user.profile.school
    
    if request.method == 'POST':
        form = BankStatementPatternForm(request.POST)
        if form.is_valid():
            pattern = form.save(commit=False)
            pattern.school = school
            pattern.save()
            messages.success(request, f'Bank statement pattern "{pattern.pattern_name}" created successfully.')
            # Redirect back to list, preserving school parameter if present
            if school_token:
                return redirect(f"{reverse('receivables:bank_statement_pattern_list')}?school={school_token}")
            return redirect('receivables:bank_statement_pattern_list')
    else:
        form = BankStatementPatternForm(initial={'school': school})
        form.fields['school'].widget.attrs['readonly'] = True
    
    context = {
        'form': form,
        'title': 'Create Bank Statement Pattern',
        'school': school,
    }
    if school_token:
        context['school_token'] = school_token
    return render(request, 'receivables/bank_statement_pattern_form.html', context)


@login_required
def bank_statement_pattern_edit(request, pattern_id):
    """Edit a bank statement pattern"""
    from receivables.forms import BankStatementPatternForm
    from core.models import School
    
    # Allow superadmins to edit patterns for a specific school via query parameter
    school_token = request.GET.get('school', '')
    if school_token and (request.user.is_superuser or request.user.profile.roles.filter(name='super_admin').exists()):
        target_school = School.from_signed_token(school_token)
        if target_school:
            # Superadmin can edit patterns for the specified school
            pattern = _get_pattern_from_token_or_id(request, pattern_id)
            if pattern and pattern.school == target_school:
                school = target_school
            else:
                school = request.user.profile.school
                pattern = _get_pattern_from_token_or_id(request, pattern_id)
        else:
            school = request.user.profile.school
            pattern = _get_pattern_from_token_or_id(request, pattern_id)
    else:
        school = request.user.profile.school
        pattern = _get_pattern_from_token_or_id(request, pattern_id)
    
    if request.method == 'POST':
        form = BankStatementPatternForm(request.POST, instance=pattern)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank statement pattern updated successfully.')
            # Check if we came from school admin page
            school_token = request.GET.get('school', '')
            if school_token:
                return redirect(f"{reverse('receivables:bank_statement_pattern_list')}?school={school_token}")
            return redirect('receivables:bank_statement_pattern_list')
    else:
        form = BankStatementPatternForm(instance=pattern)
        # School is hidden, so no need to set readonly
    
    context = {
        'form': form,
        'title': 'Edit Bank Statement Pattern',
        'pattern': pattern,
        'school': school,
    }
    school_token = request.GET.get('school', '')
    if school_token:
        context['school_token'] = school_token
    return render(request, 'receivables/bank_statement_pattern_form.html', context)


@login_required
def bank_statement_pattern_delete(request, pattern_id):
    """Delete a bank statement pattern"""
    from core.models import School
    
    # Allow superadmins to delete patterns for a specific school via query parameter
    school_token = request.GET.get('school', '')
    if school_token and (request.user.is_superuser or request.user.profile.roles.filter(name='super_admin').exists()):
        target_school = School.from_signed_token(school_token)
        if target_school:
            # Superadmin can delete patterns for the specified school
            pattern = _get_pattern_from_token_or_id(request, pattern_id)
            if not pattern or pattern.school != target_school:
                from django.http import Http404
                raise Http404("Pattern not found")
        else:
            pattern = _get_pattern_from_token_or_id(request, pattern_id)
    else:
        pattern = _get_pattern_from_token_or_id(request, pattern_id)
    
    if request.method == 'POST':
        pattern_name = pattern.pattern_name
        pattern.delete()
        messages.success(request, f'Bank statement pattern "{pattern_name}" deleted successfully.')
        # Check if we came from school admin page
        school_token = request.GET.get('school', '')
        if school_token:
            return redirect(f"{reverse('receivables:bank_statement_pattern_list')}?school={school_token}")
        return redirect('receivables:bank_statement_pattern_list')
    
    context = {'pattern': pattern}
    if school_token:
        context['school_token'] = school_token
    return render(request, 'receivables/bank_statement_pattern_confirm_delete.html', context)


# ==================== Bank Statement Upload Views ====================

@login_required
def bank_statement_upload(request):
    """Upload and process bank statement"""
    school = request.user.profile.school
    patterns = BankStatementPattern.objects.filter(school=school, is_active=True).order_by('bank_name', 'pattern_name')
    
    if request.method == 'POST':
        pattern_id = request.POST.get('pattern_id')
        statement_file = request.FILES.get('statement_file')
        
        if not pattern_id or not statement_file:
            messages.error(request, 'Please select a pattern and upload a file.')
            return redirect('receivables:bank_statement_upload')
        
        try:
            pattern = BankStatementPattern.objects.get(school=school, id=pattern_id, is_active=True)
        except BankStatementPattern.DoesNotExist:
            messages.error(request, 'Selected pattern not found.')
            return redirect('receivables:bank_statement_upload')
        
        # Create upload record
        upload = BankStatementUpload.objects.create(
            school=school,
            pattern=pattern,
            file_name=statement_file.name,
            uploaded_by=request.user,
            status='processing'
        )
        
        # Process the statement asynchronously (or synchronously for now)
        try:
            result = process_bank_statement(upload, statement_file, pattern)
            upload.status = 'completed'
            upload.total_transactions = result.get('total_transactions', 0)
            upload.matched_payments = result.get('matched_payments', 0)
            upload.unmatched_payments = result.get('unmatched_payments', 0)
            upload.duplicate_transactions = result.get('duplicate_transactions', 0)
            upload.processed_at = timezone.now()
            upload.save()
            
            # Build success message with all counts
            duplicate_count = result.get("duplicate_transactions", 0)
            message_parts = [
                f'Bank statement processed successfully. '
                f'Total: {result.get("total_transactions", 0)}, '
                f'Matched: {result.get("matched_payments", 0)}, '
                f'Unmatched: {result.get("unmatched_payments", 0)}'
            ]
            if duplicate_count > 0:
                message_parts.append(f'Duplicates: {duplicate_count}')
            
            messages.success(request, ', '.join(message_parts))
        except Exception as e:
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            messages.error(request, f'Error processing bank statement: {str(e)}')
        
        # Redirect back to upload page to show results and allow another upload
        return redirect('receivables:bank_statement_upload')
    
    # Get recent uploads
    recent_uploads = BankStatementUpload.objects.filter(school=school).order_by('-uploaded_at')[:10]
    
    context = {
        'patterns': patterns,
        'recent_uploads': recent_uploads,
    }
    
    return render(request, 'receivables/bank_statement_upload.html', context)


def process_bank_statement(upload, statement_file, pattern):
    """Process bank statement file and match payments"""
    import csv
    import re
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    from django.db.models import F
    
    result = {
        'total_transactions': 0,
        'matched_payments': 0,
        'unmatched_payments': 0,
        'duplicate_transactions': 0,
        'transactions': []
    }
    
    # Read CSV file
    content = statement_file.read()
    if pattern.encoding != 'utf-8':
        try:
            content = content.decode(pattern.encoding).encode('utf-8')
        except:
            content = content.decode('utf-8', errors='ignore').encode('utf-8')
    else:
        content = content.decode('utf-8', errors='ignore').encode('utf-8')
    
    csv_content = content.decode('utf-8')
    lines = csv_content.split('\n')
    
    # Skip header if present
    start_line = 1 if pattern.has_header else 0
    
    # Determine delimiter
    delimiter = ',' if pattern.delimiter == ',' else (';' if pattern.delimiter == ';' else '\t')
    
    # Process each line
    for line_num, line in enumerate(lines[start_line:], start=start_line + 1):
        if not line.strip():
            continue
        
        try:
            reader = csv.reader([line], delimiter=delimiter)
            row = next(reader)
            
            if len(row) < 2:
                continue
            
            # Extract data based on pattern
            date_str = extract_column_value(row, pattern.date_column)
            amount_str = extract_column_value(row, pattern.amount_column)
            reference_str = extract_column_value(row, pattern.reference_column) if pattern.reference_column else ''
            transaction_ref_str = extract_column_value(row, pattern.transaction_reference_column) if pattern.transaction_reference_column else ''
            
            # Parse date
            try:
                transaction_date = datetime.strptime(date_str, pattern.date_format).date()
            except:
                continue
            
            # Parse amount
            try:
                # Remove currency symbols and commas
                amount_str_clean = re.sub(r'[^\d.-]', '', amount_str)
                amount = Decimal(amount_str_clean)
            except (InvalidOperation, ValueError):
                continue
            
            # Extract M-Pesa details from narrative
            mpesa_details = {}
            if reference_str:
                mpesa_details = pattern.extract_mpesa_details(reference_str)
            
            # Extract student ID from reference using pattern's extract method
            student_id = None
            if reference_str:
                student_id = pattern.extract_student_id(reference_str)
                # Also check if student_id was extracted from mpesa_details
                if not student_id and mpesa_details.get('student_id'):
                    student_id = mpesa_details.get('student_id')
            
            # Get bank reference number - prioritize transaction_reference_column if available
            bank_reference = transaction_ref_str.strip() if transaction_ref_str else ''
            # If no transaction reference column, try M-Pesa reference from narrative
            if not bank_reference and mpesa_details:
                bank_reference = mpesa_details.get('mpesa_reference', '')
            # If still no reference, try to extract from narrative
            if not bank_reference and reference_str:
                # Try to find any alphanumeric reference in the narrative
                ref_match = re.search(r'\b([A-Z0-9]{8,15})\b', reference_str)
                if ref_match:
                    bank_reference = ref_match.group(1)
            
            # Check for duplicate transactions using bank_reference_number or mpesa_reference
            is_duplicate = False
            
            # Check by M-Pesa reference first (most reliable)
            if mpesa_details.get('mpesa_reference'):
                mpesa_ref = mpesa_details.get('mpesa_reference')
                
                # Check unmatched transactions
                existing_unmatched = UnmatchedTransaction.objects.filter(
                    school=upload.school,
                    mpesa_reference=mpesa_ref
                ).first()
                if existing_unmatched:
                    result['duplicate_transactions'] += 1
                    is_duplicate = True
                
                # Check payments by transaction_id (where M-Pesa reference is stored)
                if not is_duplicate:
                    existing_payment = Payment.objects.filter(
                        school=upload.school,
                        transaction_id=mpesa_ref
                    ).first()
                    if existing_payment:
                        result['duplicate_transactions'] += 1
                        is_duplicate = True
                
                # Also check payments by reference_number containing M-Pesa ref (backup check)
                if not is_duplicate:
                    existing_payment = Payment.objects.filter(
                        school=upload.school,
                        reference_number__icontains=mpesa_ref
                    ).first()
                    if existing_payment:
                        result['duplicate_transactions'] += 1
                        is_duplicate = True
            
            # Also check by bank reference number if available and not already duplicate
            if not is_duplicate and bank_reference:
                # Check unmatched transactions
                existing_unmatched = UnmatchedTransaction.objects.filter(
                    school=upload.school,
                    bank_reference_number=bank_reference
                ).first()
                if existing_unmatched:
                    result['duplicate_transactions'] += 1
                    is_duplicate = True
                
                # Check payments by bank_reference in reference_number or transaction_id
                # Some banks might store the transaction reference in these fields
                if not is_duplicate:
                    existing_payment = Payment.objects.filter(
                        school=upload.school
                    ).filter(
                        Q(transaction_id=bank_reference) | 
                        Q(reference_number__icontains=bank_reference)
                    ).first()
                    if existing_payment:
                        result['duplicate_transactions'] += 1
                        is_duplicate = True
            
            result['total_transactions'] += 1
            
            # Skip if duplicate
            if is_duplicate:
                result['transactions'].append({
                    'transaction_id': f"{upload.id}-{line_num}",
                    'student_id': student_id,
                    'amount': float(amount),
                    'payment_date': transaction_date.isoformat(),
                    'narrative': reference_str,
                    'status': 'Duplicate'
                })
                continue
            
            # Try to match with existing payment or create payment from receivable
            matched = False
            if student_id:
                # Try to find student and match payment
                try:
                    student = Student.objects.get(school=upload.school, student_id=student_id)
                    
                    # Debug logging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f'Processing transaction: student_id={student_id}, amount={amount}, date={transaction_date}, reference={reference_str[:50]}')
                    
                    # Additional duplicate check - check by M-Pesa reference in transaction_id
                    if mpesa_details.get('mpesa_reference'):
                        existing_payment = Payment.objects.filter(
                            school=upload.school,
                            transaction_id=mpesa_details.get('mpesa_reference')
                        ).first()
                        if existing_payment:
                            result['duplicate_transactions'] += 1
                            matched = True
                    
                    # Also check by bank_reference_number if available
                    if not matched and bank_reference:
                        existing_payment = Payment.objects.filter(
                            school=upload.school
                        ).filter(
                            Q(transaction_id=bank_reference) | 
                            Q(reference_number__icontains=bank_reference)
                        ).first()
                        if existing_payment:
                            result['duplicate_transactions'] += 1
                            matched = True
                    
                    # Also check by amount, date, student, and reference (legacy check for non-M-Pesa)
                    if not matched:
                        existing_payment = Payment.objects.filter(
                            school=upload.school,
                            student=student,
                            amount=amount,
                            payment_date__date=transaction_date,
                            reference_number__icontains=reference_str[:50] if reference_str else ''
                        ).first()
                        
                        if existing_payment:
                            result['duplicate_transactions'] += 1
                            matched = True
                            logger.info(f'Found duplicate payment by legacy check: payment_id={existing_payment.payment_id}')
                    
                    if not matched:
                        # Try to match to outstanding receivables (StudentFee with amount_charged > amount_paid)
                        # Note: We check is_paid=False OR amount_charged > amount_paid to catch edge cases
                        # where is_paid might be incorrectly set to True
                        outstanding_fees = StudentFee.objects.filter(
                            school=upload.school,
                            student=student
                        ).filter(
                            amount_charged__gt=F('amount_paid')
                        ).order_by('due_date', 'created_at')
                        
                        # Debug logging
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f'Found {outstanding_fees.count()} outstanding fees for student {student_id}')
                        for fee in outstanding_fees:
                            outstanding = fee.amount_charged - fee.amount_paid
                            logger.info(f'  Fee ID {fee.id}: charged={fee.amount_charged}, paid={fee.amount_paid}, outstanding={outstanding}, transaction_amount={amount}')
                        
                        # Calculate total outstanding
                        total_outstanding = sum(float(fee.amount_charged - fee.amount_paid) for fee in outstanding_fees)
                        logger.info(f'Total outstanding for student {student_id}: {total_outstanding}, transaction amount: {amount}')
                        
                        # Strategy: Try to match to multiple fees if payment covers them
                        matched_fees = []  # List of (fee, amount_to_allocate) tuples
                        remaining_amount = float(amount)
                        
                        # Sort fees by due date (oldest first) and then by amount (smallest first)
                        # This prioritizes clearing older/smaller fees first
                        fees_sorted = sorted(outstanding_fees, key=lambda f: (f.due_date, float(f.amount_charged - f.amount_paid)))
                        
                        # Try to allocate payment across multiple fees
                        for fee in fees_sorted:
                            if remaining_amount <= 0.01:  # Less than 1 cent remaining
                                break
                            
                            outstanding = float(fee.amount_charged - fee.amount_paid)
                            if outstanding <= 0:
                                continue
                            
                            # Allocate what we can to this fee
                            amount_to_allocate = min(remaining_amount, outstanding)
                            matched_fees.append((fee, amount_to_allocate))
                            remaining_amount -= amount_to_allocate
                            logger.info(f'  Allocating {amount_to_allocate} to fee ID {fee.id} (outstanding: {outstanding}), remaining: {remaining_amount}')
                        
                        # If we matched to fees, use the first one as the primary fee for the payment record
                        # (Payment model requires a single student_fee, but we'll create allocations for all)
                        matched_fee = matched_fees[0][0] if matched_fees else None
                        
                        if matched_fee:
                            # Final duplicate check before creating payment - comprehensive check
                            final_duplicate_check = False
                            
                            # Check by M-Pesa reference in transaction_id
                            if mpesa_details.get('mpesa_reference'):
                                existing_payment = Payment.objects.filter(
                                    school=upload.school,
                                    transaction_id=mpesa_details.get('mpesa_reference')
                                ).first()
                                if existing_payment:
                                    result['duplicate_transactions'] += 1
                                    final_duplicate_check = True
                                    matched = True
                            
                            # Check by bank_reference_number if available
                            if not final_duplicate_check and bank_reference:
                                existing_payment = Payment.objects.filter(
                                    school=upload.school
                                ).filter(
                                    Q(transaction_id=bank_reference) | 
                                    Q(reference_number__icontains=bank_reference)
                                ).first()
                                if existing_payment:
                                    result['duplicate_transactions'] += 1
                                    final_duplicate_check = True
                                    matched = True
                            
                            # Final check by amount, date, student, and reference
                            if not final_duplicate_check:
                                existing_payment = Payment.objects.filter(
                                    school=upload.school,
                                    student=student,
                                    amount=amount,
                                    payment_date__date=transaction_date,
                                    reference_number__icontains=reference_str[:50] if reference_str else ''
                                ).first()
                                if existing_payment:
                                    result['duplicate_transactions'] += 1
                                    final_duplicate_check = True
                                    matched = True
                            
                            if not final_duplicate_check:
                                try:
                                    # Create payment record
                                    from django.utils import timezone as tz
                                    from receivables.models import Credit
                                    # Build reference number with M-Pesa details if available
                                    payment_ref = reference_str[:100] if reference_str else ''
                                    if mpesa_details.get('mpesa_reference'):
                                        payment_ref = f"M-Pesa: {mpesa_details.get('mpesa_reference')} - {payment_ref}"
                                    
                                    # Allocate payment across multiple fees if possible
                                    # Sort fees by due date (oldest first) to prioritize clearing older fees
                                    fees_to_allocate = sorted(outstanding_fees, key=lambda f: (f.due_date, float(f.amount_charged - f.amount_paid)))
                                    
                                    remaining_amount = float(amount)
                                    allocations = []  # List of (fee, amount) tuples
                                    
                                    # Allocate payment across fees
                                    for fee in fees_to_allocate:
                                        if remaining_amount <= 0.01:  # Less than 1 cent remaining
                                            break
                                        
                                        outstanding = float(fee.amount_charged - fee.amount_paid)
                                        if outstanding <= 0:
                                            continue
                                        
                                        # Allocate what we can to this fee
                                        amount_to_allocate = min(remaining_amount, outstanding)
                                        allocations.append((fee, amount_to_allocate))
                                        remaining_amount -= amount_to_allocate
                                        logger.info(f'  Planning allocation: {amount_to_allocate} to fee ID {fee.id} (outstanding: {outstanding}), remaining: {remaining_amount}')
                                    
                                    # Use the first fee as primary for payment record (Payment model requires a single student_fee)
                                    primary_fee = allocations[0][0] if allocations else matched_fee
                                    overpayment_amount = remaining_amount
                                    
                                    logger.info(f'Allocating payment: amount={amount}, {len(allocations)} fee(s), overpayment={overpayment_amount}')
                                    
                                    # Use database transaction to ensure consistency
                                    from django.db import transaction as db_transaction
                                    
                                    with db_transaction.atomic():
                                        # Update all fees that will receive allocation
                                        for fee, alloc_amount in allocations:
                                            fee.amount_paid += Decimal(str(alloc_amount))
                                            if fee.amount_paid >= fee.amount_charged:
                                                fee.is_paid = True
                                            fee.save()
                                        
                                        # Create payment record with the full amount
                                        payment = Payment.objects.create(
                                            school=upload.school,
                                            student=student,
                                            student_fee=primary_fee,  # Primary fee for payment record
                                            amount=amount,  # Full payment amount
                                            payment_method='bank_transfer',
                                            status='completed',
                                            reference_number=payment_ref[:100],
                                            transaction_id=mpesa_details.get('mpesa_reference', '')[:50] if mpesa_details else '',
                                            payment_date=tz.make_aware(datetime.combine(transaction_date, datetime.min.time())),
                                            processed_by=upload.uploaded_by,
                                            notes=f'Auto-matched from bank statement upload: {upload.file_name}'
                                        )
                                        
                                        # Create allocations for all fees
                                        from receivables.models import PaymentAllocation
                                        for fee, alloc_amount in allocations:
                                            PaymentAllocation.objects.get_or_create(
                                                school=upload.school,
                                                payment=payment,
                                                student_fee=fee,
                                                defaults={
                                                    'amount_allocated': Decimal(str(alloc_amount)),
                                                    'created_by': upload.uploaded_by
                                                }
                                            )
                                            logger.info(f'  Created allocation: {alloc_amount} to fee ID {fee.id}')
                                        
                                        # Create credit for overpayment if any (only after allocating to all possible fees)
                                        if overpayment_amount > 0.01:  # Only create credit if overpayment is more than 1 cent
                                            Credit.objects.create(
                                                school=upload.school,
                                                student=student,
                                                amount=Decimal(str(overpayment_amount)),
                                                source='overpayment',
                                                payment=payment,
                                                description=f'Overpayment from bank statement upload: {upload.file_name}. Payment amount: {amount}, Allocated to {len(allocations)} fee(s), Remaining: {overpayment_amount}',
                                                created_by=upload.uploaded_by
                                            )
                                            logger.info(f'Created credit of {overpayment_amount} for student {student_id} (remaining after allocating to {len(allocations)} fees)')
                                    
                                    result['matched_payments'] += 1
                                    matched = True
                                except Exception as payment_error:
                                    # Log the error and create unmatched transaction
                                    import logging
                                    logger = logging.getLogger(__name__)
                                    logger.error(f'Error creating payment for student {student_id}, amount {amount}: {str(payment_error)}', exc_info=True)
                                    
                                    # Rollback student fee update if payment creation failed
                                    matched_fee.amount_paid -= amount
                                    if matched_fee.amount_paid < matched_fee.amount_charged:
                                        matched_fee.is_paid = False
                                    matched_fee.save()
                                    
                                    # Create unmatched transaction with error note
                                    UnmatchedTransaction.objects.create(
                                        school=upload.school,
                                        upload=upload,
                                        transaction_date=transaction_date,
                                        amount=amount,
                                        reference_number=reference_str[:200] if reference_str else '',
                                        bank_reference_number=bank_reference[:100] if bank_reference else None,
                                        mpesa_reference=mpesa_details.get('mpesa_reference', '')[:50] if mpesa_details else None,
                                        mobile_number=mpesa_details.get('mobile_number', '')[:15] if mpesa_details else None,
                                        extracted_student_id=student_id,
                                        transaction_type='credit',
                                        status='unmatched',
                                        notes=f'Payment creation failed: {str(payment_error)}'
                                    )
                                    result['unmatched_payments'] += 1
                        else:
                            # No matching receivable found - create unmatched transaction
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f'No matching receivable found for student {student_id}, amount {amount}. Outstanding fees count: {outstanding_fees.count()}')
                            for fee in outstanding_fees:
                                outstanding = fee.amount_charged - fee.amount_paid
                                logger.warning(f'  Fee ID {fee.id}: outstanding={outstanding}, transaction_amount={amount}, difference={abs(float(amount) - float(outstanding))}')
                            UnmatchedTransaction.objects.create(
                                school=upload.school,
                                upload=upload,
                                transaction_date=transaction_date,
                                amount=amount,
                                reference_number=reference_str[:200] if reference_str else '',
                                bank_reference_number=bank_reference[:100] if bank_reference else None,
                                mpesa_reference=mpesa_details.get('mpesa_reference', '')[:50] if mpesa_details else None,
                                mobile_number=mpesa_details.get('mobile_number', '')[:15] if mpesa_details else None,
                                extracted_student_id=student_id,
                                transaction_type='credit',
                                status='unmatched',
                                notes=f'No matching receivable found. Student has {outstanding_fees.count()} outstanding fee(s) but amounts do not match.'
                            )
                            result['unmatched_payments'] += 1
                except Student.DoesNotExist:
                    # Create unmatched transaction record - student not found
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Student not found: student_id={student_id}, school={upload.school.name}')
                    UnmatchedTransaction.objects.create(
                        school=upload.school,
                        upload=upload,
                        transaction_date=transaction_date,
                        amount=amount,
                        reference_number=reference_str[:200] if reference_str else '',
                        bank_reference_number=bank_reference[:100] if bank_reference else None,
                        mpesa_reference=mpesa_details.get('mpesa_reference', '')[:50] if mpesa_details else None,
                        mobile_number=mpesa_details.get('mobile_number', '')[:15] if mpesa_details else None,
                        extracted_student_id=student_id,
                        transaction_type='credit',
                        status='unmatched',
                        notes=f'Student with ID {student_id} not found in school {upload.school.name}'
                    )
                    result['unmatched_payments'] += 1
            else:
                # Create unmatched transaction record - no student ID extracted
                UnmatchedTransaction.objects.create(
                    school=upload.school,
                    upload=upload,
                    transaction_date=transaction_date,
                    amount=amount,
                    reference_number=reference_str[:200] if reference_str else '',
                    bank_reference_number=bank_reference[:100] if bank_reference else None,
                    mpesa_reference=mpesa_details.get('mpesa_reference', '')[:50] if mpesa_details else None,
                    mobile_number=mpesa_details.get('mobile_number', '')[:15] if mpesa_details else None,
                    extracted_student_id=None,
                    transaction_type='credit',
                    status='unmatched'
                )
                result['unmatched_payments'] += 1
            
            result['transactions'].append({
                'transaction_id': f"{upload.id}-{line_num}",
                'student_id': student_id,
                'amount': float(amount),
                'payment_date': transaction_date.isoformat(),
                'narrative': reference_str,
                'status': 'Matched' if matched else 'Unmatched'
            })
            
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error processing bank statement line {line_num}: {str(e)}', exc_info=True)
            # Create unmatched transaction for error cases
            try:
                UnmatchedTransaction.objects.create(
                    school=upload.school,
                    upload=upload,
                    transaction_date=transaction_date if 'transaction_date' in locals() else timezone.now().date(),
                    amount=amount if 'amount' in locals() else Decimal('0.00'),
                    reference_number=reference_str[:200] if 'reference_str' in locals() and reference_str else '',
                    bank_reference_number=bank_reference[:100] if 'bank_reference' in locals() and bank_reference else None,
                    mpesa_reference=mpesa_details.get('mpesa_reference', '')[:50] if 'mpesa_details' in locals() and mpesa_details else None,
                    mobile_number=mpesa_details.get('mobile_number', '')[:15] if 'mpesa_details' in locals() and mpesa_details else None,
                    extracted_student_id=student_id if 'student_id' in locals() else None,
                    transaction_type='credit',
                    status='unmatched',
                    notes=f'Error during processing: {str(e)}'
                )
                result['unmatched_payments'] += 1
            except Exception as create_error:
                logger.error(f'Failed to create unmatched transaction: {str(create_error)}')
            continue
    
    return result


def extract_column_value(row, column_spec):
    """Extract value from row based on column specification (name or index)"""
    if not column_spec:
        return ''
    
    # Try as index first
    try:
        index = int(column_spec)
        if 0 <= index < len(row):
            return row[index].strip()
    except ValueError:
        pass
    
    # Try as column name
    try:
        index = row.index(column_spec)
        return row[index].strip()
    except (ValueError, AttributeError):
        pass
    
    return ''


# ==================== Unmatched Transactions Views ====================

@login_required
def unmatched_transaction_list(request):
    """List all unmatched transactions with search and filter functionality"""
    from core.decorators import permission_required
    from django.db.models import Sum
    school = request.user.profile.school
    transactions = UnmatchedTransaction.objects.filter(
        school=school
    ).select_related('upload', 'matched_payment', 'matched_student', 'matched_by').order_by('-transaction_date', '-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        transactions = transactions.filter(
            Q(reference_number__icontains=search_query) |
            Q(extracted_student_id__icontains=search_query) |
            Q(matched_student__student_id__icontains=search_query) |
            Q(matched_student__first_name__icontains=search_query) |
            Q(matched_student__last_name__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    # Filter by date range
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        transactions = transactions.filter(transaction_date__gte=date_from)
    if date_to:
        transactions = transactions.filter(transaction_date__lte=date_to)
    
    # Calculate totals
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    unmatched_count = transactions.filter(status='unmatched').count()
    matched_count = transactions.filter(status='matched').count()
    
    # Pagination
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_amount': total_amount,
        'unmatched_count': unmatched_count,
        'matched_count': matched_count,
    }
    
    return render(request, 'receivables/unmatched_transaction_list.html', context)


@login_required
def unmatched_transaction_detail(request, transaction_id):
    """View details of an unmatched transaction"""
    from core.decorators import permission_required
    transaction = _get_unmatched_transaction_from_token_or_id(request, transaction_id)
    school = transaction.school
    
    # Get potential matches
    potential_matches = []
    if transaction.extracted_student_id:
        try:
            student = Student.objects.get(school=school, student_id=transaction.extracted_student_id)
            # Find payments that might match
            potential_payments = Payment.objects.filter(
                school=school,
                student=student,
                amount=transaction.amount,
                payment_date__date=transaction.transaction_date,
                status='completed'
            ).exclude(
                matched_transactions__isnull=False
            ).order_by('-payment_date')[:10]
            
            potential_matches = [
                {
                    'payment': payment,
                    'match_score': 100 if payment.reference_number and transaction.reference_number and payment.reference_number in transaction.reference_number else 80
                }
                for payment in potential_payments
            ]
        except Student.DoesNotExist:
            pass
    
    context = {
        'transaction': transaction,
        'potential_matches': potential_matches,
    }
    
    return render(request, 'receivables/unmatched_transaction_detail.html', context)


@login_required
def unmatched_transaction_match(request, transaction_id):
    """Match an unmatched transaction to a payment"""
    from core.decorators import permission_required
    transaction = _get_unmatched_transaction_from_token_or_id(request, transaction_id)
    school = transaction.school
    
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        student_id = request.POST.get('student_id')
        student_fee_id = request.POST.get('student_fee_id')  # Optional: specific fee to allocate to
        
        try:
            from django.db import transaction as db_transaction
            from django.utils import timezone as tz
            from receivables.models import Credit, PaymentAllocation
            from core.models import StudentFee
            from django.db.models import F
            
            if payment_id:
                # Match to existing payment
                payment = _get_payment_from_token_or_id(request, payment_id)
                transaction.matched_payment = payment
                transaction.matched_student = payment.student
                messages.success(request, 'Transaction matched to existing payment.')
            elif student_id:
                # Match to student - create payment and handle allocation/credits
                student = Student.objects.get(school=school, student_id=student_id)
                transaction.matched_student = student
                
                with db_transaction.atomic():
                    # Build reference number
                    payment_ref = transaction.reference_number[:100] if transaction.reference_number else ''
                    if transaction.mpesa_reference:
                        payment_ref = f"M-Pesa: {transaction.mpesa_reference} - {payment_ref}"
                    
                    # Check for outstanding receivables
                    outstanding_fees = StudentFee.objects.filter(
                        school=school,
                        student=student,
                        amount_charged__gt=F('amount_paid')
                    ).order_by('due_date', 'created_at')
                    
                    payment = None
                    total_outstanding = sum(float(fee.amount_charged - fee.amount_paid) for fee in outstanding_fees)
                    
                    if student_fee_id:
                        # Allocate to specific fee
                        matched_fee = StudentFee.objects.get(id=student_fee_id, school=school, student=student)
                        outstanding_amount = matched_fee.amount_charged - matched_fee.amount_paid
                        amount_to_allocate = min(float(transaction.amount), float(outstanding_amount))
                        overpayment_amount = float(transaction.amount) - amount_to_allocate
                        
                        # Update fee
                        matched_fee.amount_paid += Decimal(str(amount_to_allocate))
                        if matched_fee.amount_paid >= matched_fee.amount_charged:
                            matched_fee.is_paid = True
                        matched_fee.save()
                        
                        # Create payment
                        payment = Payment.objects.create(
                            school=school,
                            student=student,
                            student_fee=matched_fee,
                            amount=transaction.amount,
                            payment_method='bank_transfer',
                            status='completed',
                            reference_number=payment_ref[:100],
                            transaction_id=transaction.mpesa_reference[:50] if transaction.mpesa_reference else '',
                            payment_date=tz.make_aware(datetime.combine(transaction.transaction_date, datetime.min.time())),
                            processed_by=request.user,
                            notes=f'Matched from unmatched transaction: {transaction.reference_number[:50]}'
                        )
                        
                        # Create allocation
                        PaymentAllocation.objects.get_or_create(
                            school=school,
                            payment=payment,
                            student_fee=matched_fee,
                            defaults={
                                'amount_allocated': Decimal(str(amount_to_allocate)),
                                'created_by': request.user
                            }
                        )
                        
                        # Create credit for overpayment if any
                        if overpayment_amount > 0.01:
                            Credit.objects.create(
                                school=school,
                                student=student,
                                amount=Decimal(str(overpayment_amount)),
                                source='overpayment',
                                payment=payment,
                                description=f'Overpayment from unmatched transaction match. Payment amount: {transaction.amount}, Fee outstanding: {outstanding_amount}',
                                created_by=request.user
                            )
                            messages.success(request, f'Payment of KES {transaction.amount} matched. KES {amount_to_allocate} allocated to fee, KES {overpayment_amount} credited.')
                        else:
                            messages.success(request, f'Payment of KES {transaction.amount} matched and allocated to fee.')
                    
                    elif outstanding_fees.exists():
                        # Allocate to largest outstanding fee
                        fees_sorted = sorted(outstanding_fees, key=lambda f: float(f.amount_charged - f.amount_paid), reverse=True)
                        matched_fee = fees_sorted[0]
                        outstanding_amount = matched_fee.amount_charged - matched_fee.amount_paid
                        amount_to_allocate = min(float(transaction.amount), float(outstanding_amount))
                        overpayment_amount = float(transaction.amount) - amount_to_allocate
                        
                        # Update fee
                        matched_fee.amount_paid += Decimal(str(amount_to_allocate))
                        if matched_fee.amount_paid >= matched_fee.amount_charged:
                            matched_fee.is_paid = True
                        matched_fee.save()
                        
                        # Create payment
                        payment = Payment.objects.create(
                            school=school,
                            student=student,
                            student_fee=matched_fee,
                            amount=transaction.amount,
                            payment_method='bank_transfer',
                            status='completed',
                            reference_number=payment_ref[:100],
                            transaction_id=transaction.mpesa_reference[:50] if transaction.mpesa_reference else '',
                            payment_date=tz.make_aware(datetime.combine(transaction.transaction_date, datetime.min.time())),
                            processed_by=request.user,
                            notes=f'Matched from unmatched transaction: {transaction.reference_number[:50]}'
                        )
                        
                        # Create allocation
                        PaymentAllocation.objects.get_or_create(
                            school=school,
                            payment=payment,
                            student_fee=matched_fee,
                            defaults={
                                'amount_allocated': Decimal(str(amount_to_allocate)),
                                'created_by': request.user
                            }
                        )
                        
                        # Create credit for overpayment if any
                        if overpayment_amount > 0.01:
                            Credit.objects.create(
                                school=school,
                                student=student,
                                amount=Decimal(str(overpayment_amount)),
                                source='overpayment',
                                payment=payment,
                                description=f'Overpayment from unmatched transaction match. Payment amount: {transaction.amount}, Fee outstanding: {outstanding_amount}',
                                created_by=request.user
                            )
                            messages.success(request, f'Payment of KES {transaction.amount} matched. KES {amount_to_allocate} allocated to fee, KES {overpayment_amount} credited.')
                        else:
                            messages.success(request, f'Payment of KES {transaction.amount} matched and allocated to fee.')
                    
                    else:
                        # No outstanding receivables - create credit for full amount
                        # Find any fee for the student (for payment record requirement) or create a dummy allocation
                        # Since Payment requires student_fee, we'll use the most recent fee or create a special handling
                        any_fee = StudentFee.objects.filter(school=school, student=student).order_by('-created_at').first()
                        
                        if any_fee:
                            # Use the most recent fee (even if paid) for the payment record
                            payment = Payment.objects.create(
                                school=school,
                                student=student,
                                student_fee=any_fee,
                                amount=transaction.amount,
                                payment_method='bank_transfer',
                                status='completed',
                                reference_number=payment_ref[:100],
                                transaction_id=transaction.mpesa_reference[:50] if transaction.mpesa_reference else '',
                                payment_date=tz.make_aware(datetime.combine(transaction.transaction_date, datetime.min.time())),
                                processed_by=request.user,
                                notes=f'Matched from unmatched transaction (no outstanding fees): {transaction.reference_number[:50]}'
                            )
                            
                            # Don't create allocation - full amount goes to credit
                        else:
                            # Student has no fees at all - this shouldn't happen but handle it
                            # We can't create a payment without a student_fee, so create a credit directly
                            # But we still need a payment record for tracking
                            # Create a minimal payment record with a note
                            from core.models import FeeCategory, Term
                            # This is a fallback - ideally student should have fees
                            messages.warning(request, 'Student has no fees. Creating credit only.')
                            payment = None
                        
                        # Create credit for full amount
                        Credit.objects.create(
                            school=school,
                            student=student,
                            amount=transaction.amount,
                            source='overpayment',
                            payment=payment,
                            description=f'Payment matched from unmatched transaction with no outstanding receivables. Full amount credited for future application.',
                            created_by=request.user
                        )
                        if payment:
                            messages.success(request, f'Payment of KES {transaction.amount} matched. No outstanding fees found - full amount credited for future application.')
                        else:
                            messages.success(request, f'Credit of KES {transaction.amount} created. No payment record created (student has no fees).')
                    
                    # Link transaction to payment
                    transaction.matched_payment = payment
            
            # Update notes if provided
            notes = request.POST.get('notes', '')
            if notes:
                transaction.notes = notes
            
            transaction.status = 'matched'
            transaction.matched_by = request.user
            transaction.matched_at = timezone.now()
            transaction.save()
            
            return redirect('receivables:unmatched_transaction_detail', transaction_id=transaction.get_signed_token())
            
        except Payment.DoesNotExist:
            messages.error(request, 'Payment not found.')
        except Student.DoesNotExist:
            messages.error(request, 'Student not found.')
        except StudentFee.DoesNotExist:
            messages.error(request, 'Student fee not found.')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error matching transaction: {str(e)}', exc_info=True)
            messages.error(request, f'Error matching transaction: {str(e)}')
    
    school = transaction.school
    # Get potential matches
    potential_payments = []
    if transaction.extracted_student_id:
        try:
            student = Student.objects.get(school=school, student_id=transaction.extracted_student_id)
            potential_payments = Payment.objects.filter(
                school=school,
                student=student,
                status='completed'
            ).order_by('-payment_date')[:20]
        except Student.DoesNotExist:
            pass
    
    # Get all students for manual selection
    students = Student.objects.filter(school=school, is_active=True).order_by('student_id')[:100]
    
    context = {
        'transaction': transaction,
        'potential_payments': potential_payments,
        'students': students,
    }
    
    return render(request, 'receivables/unmatched_transaction_match.html', context)


@login_required
def unmatched_transaction_ignore(request, transaction_id):
    """Mark an unmatched transaction as ignored"""
    from core.decorators import permission_required
    transaction = _get_unmatched_transaction_from_token_or_id(request, transaction_id)
    
    if request.method == 'POST':
        transaction.status = 'ignored'
        transaction.matched_by = request.user
        transaction.matched_at = timezone.now()
        transaction.save()
        
        messages.success(request, 'Transaction marked as ignored.')
        return redirect('receivables:unmatched_transaction_list')
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'receivables/unmatched_transaction_ignore.html', context)


@login_required
def unmatched_transaction_delete(request, transaction_id):
    """Delete an unmatched transaction"""
    from core.decorators import permission_required
    transaction = _get_unmatched_transaction_from_token_or_id(request, transaction_id)
    
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Unmatched transaction deleted successfully.')
        return redirect('receivables:unmatched_transaction_list')
    
    context = {
        'transaction': transaction,
    }
    
    return render(request, 'receivables/unmatched_transaction_confirm_delete.html', context)


# ==================== API Views for Receivables ====================

@login_required
@csrf_exempt
def api_receivable_allocations(request, receivable_id):
    """API endpoint to get allocations for a receivable"""
    receivable = _get_receivable_from_token_or_id(request, receivable_id)
    school = receivable.school
    
    allocations = PaymentAllocation.objects.filter(
        school=school,
        student_fee=receivable.student_fee
    ).select_related('payment', 'payment__student').order_by('-created_at')
    
    results = []
    for alloc in allocations:
        results.append({
            'id': alloc.id,
            'amount_allocated': str(alloc.amount_allocated),
            'created_at': alloc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'payment__payment_id': str(alloc.payment.payment_id),
            'payment__token': alloc.payment.get_signed_token(),
            'payment__amount': str(alloc.payment.amount),
            'payment__payment_date': alloc.payment.payment_date.strftime('%Y-%m-%d'),
            'payment__payment_method': alloc.payment.get_payment_method_display(),
            'payment__reference_number': alloc.payment.reference_number or '',
            'payment__transaction_id': alloc.payment.transaction_id or '',
        })
    
    return JsonResponse({
        'results': results
    })


@login_required
@csrf_exempt
def api_receivable_search(request):
    """API endpoint for searching receivables"""
    school = request.user.profile.school
    search_query = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    receivables = Receivable.objects.filter(
        school=school,
        is_cleared=False
    ).select_related('student', 'student_fee__fee_category', 'student_fee__term')
    
    if search_query:
        receivables = receivables.filter(
            Q(student__student_id__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student_fee__fee_category__name__icontains=search_query)
        )
    
    paginator = Paginator(receivables, page_size)
    page_obj = paginator.get_page(page)
    
    results = []
    for rec in page_obj:
        results.append({
            'id': rec.id,
            'student_id': rec.student.student_id,
            'student_name': rec.student.full_name,
            'fee_category': rec.student_fee.fee_category.name,
            'term': f"{rec.student_fee.term.academic_year} Term {rec.student_fee.term.term_number}",
            'amount_due': float(rec.amount_due),
            'amount_paid': float(rec.amount_paid),
            'balance': float(rec.balance),
            'due_date': rec.due_date.isoformat(),
            'is_overdue': rec.is_overdue,
            'has_allocations': rec.student_fee.payment_allocations.exists(),
        })
    
    return JsonResponse({
        'results': results,
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
    })

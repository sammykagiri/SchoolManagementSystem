from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Case, When, Value, DecimalField, Count, Avg
from django.utils import timezone
from .models import Payment, MpesaPayment, PaymentReceipt, PaymentReminder
from .mpesa_service import MpesaService
from communications.services import CommunicationService
from core.models import Student, StudentFee, Term
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
    
    return render(request, 'payments/fee_summary.html', context)


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
    
    return render(request, 'payments/fee_report.html', context)


@login_required
def financial_reports(request):
    """Financial reports dashboard"""
    school = request.user.profile.school
    return render(request, 'payments/financial_reports.html', {'school': school})


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
    
    return render(request, 'payments/payment_collection_report.html', context)


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
    
    return render(request, 'payments/outstanding_fees_report.html', context)


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
    
    return render(request, 'payments/collection_summary_report.html', context)


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
    
    return render(request, 'payments/payment_method_analysis.html', context)


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

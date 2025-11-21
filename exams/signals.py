"""
Signals for exams module
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Gradebook
from .services import GradebookService


@receiver(post_save, sender=Gradebook)
def update_gradebook_summary_on_save(sender, instance, created, **kwargs):
    """
    Automatically update gradebook summary when a grade is saved.
    """
    GradebookService.update_gradebook_summary(
        instance.student,
        instance.exam.term,
        instance.exam.subject
    )


@receiver(post_delete, sender=Gradebook)
def update_gradebook_summary_on_delete(sender, instance, **kwargs):
    """
    Automatically update gradebook summary when a grade is deleted.
    """
    GradebookService.update_gradebook_summary(
        instance.student,
        instance.exam.term,
        instance.exam.subject
    )


"""
Management command to populate applicable_grades for existing subjects based on timetables.
This command extracts grades from existing timetable entries and assigns them to subjects.
"""
from django.core.management.base import BaseCommand
from timetable.models import Subject
from core.models import School


class Command(BaseCommand):
    help = 'Populate applicable_grades for existing subjects based on timetables'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id',
            type=int,
            help='ID of the school to process. If not provided, processes all schools.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating subjects',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        school_id = options.get('school_id')
        
        # Get schools to process
        if school_id:
            try:
                schools = [School.objects.get(id=school_id)]
            except School.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'School with ID {school_id} does not exist.')
                )
                return
        else:
            schools = School.objects.all()
        
        if not schools:
            self.stdout.write(
                self.style.ERROR('No schools found.')
            )
            return
        
        total_updated = 0
        
        for school in schools:
            self.stdout.write(f'\nProcessing school: {school.name} (ID: {school.id})')
            
            subjects = Subject.objects.filter(school=school)
            updated_count = 0
            
            for subject in subjects:
                # Get grades from timetables
                grades = set()
                for timetable in subject.timetables.filter(is_active=True):
                    if timetable.school_class and timetable.school_class.grade:
                        grades.add(timetable.school_class.grade)
                
                if grades:
                    if not dry_run:
                        subject.applicable_grades.set(grades)
                    
                    grade_names = ', '.join([grade.name for grade in grades])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ {subject.name}: {len(grades)} grade(s) - {grade_names}'
                        )
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  - {subject.name}: No grades found (no active timetables)'
                        )
                    )
            
            total_updated += updated_count
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'\nDRY RUN: Would update {updated_count} subject(s) for {school.name}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nUpdated {updated_count} subject(s) for {school.name}'
                    )
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n\nDRY RUN COMPLETE: Would update {total_updated} subject(s) across {len(schools)} school(s)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n\nCOMPLETE: Updated {total_updated} subject(s) across {len(schools)} school(s)'
                )
            )




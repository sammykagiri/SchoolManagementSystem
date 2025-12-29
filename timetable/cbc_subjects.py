"""
CBC Subject Templates
Predefined subjects for each CBC learning level based on Kenya's CBC curriculum.
Schools can use these templates to quickly generate subjects.
"""

# CBC Subject Templates organized by learning level
CBC_SUBJECT_TEMPLATES = {
    'early_years': [
        {
            'name': 'Language Activities',
            'code': 'LANG-EY',
            'knec_code': None,  # Early years don't have KNEC codes
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Language development and communication skills'
        },
        {
            'name': 'Mathematical Activities',
            'code': 'MATH-EY',
            'knec_code': None,
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Basic numeracy and mathematical concepts'
        },
        {
            'name': 'Environmental Activities',
            'code': 'ENV-EY',
            'knec_code': None,
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Environmental awareness and exploration'
        },
        {
            'name': 'Psychomotor and Creative Activities',
            'code': 'PCA-EY',
            'knec_code': None,
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Physical development, arts, and creativity'
        },
        {
            'name': 'Religious Education Activities',
            'code': 'RE-EY',
            'knec_code': None,
            'is_compulsory': True,
            'is_religious_education': True,
            'religious_type': 'CRE',  # Default, can be changed
            'description': 'Religious education (CRE/IRE/HRE)'
        },
    ],
    
    'lower_primary': [
        {
            'name': 'English',
            'code': 'ENG-LP',
            'knec_code': '101',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'English language and literacy'
        },
        {
            'name': 'Kiswahili',
            'code': 'KIS-LP',
            'knec_code': '102',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Kiswahili language and literacy'
        },
        {
            'name': 'Mathematics',
            'code': 'MATH-LP',
            'knec_code': '103',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Mathematics and numeracy'
        },
        {
            'name': 'Environmental Activities',
            'code': 'ENV-LP',
            'knec_code': '104',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Environmental and social studies'
        },
        {
            'name': 'Hygiene and Nutrition',
            'code': 'HYG-LP',
            'knec_code': '105',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Health, hygiene, and nutrition education'
        },
        {
            'name': 'Religious Education',
            'code': 'RE-LP',
            'knec_code': '106',
            'is_compulsory': True,
            'is_religious_education': True,
            'religious_type': 'CRE',  # Default, can be changed
            'description': 'Religious education (CRE/IRE/HRE)'
        },
        {
            'name': 'Movement and Creative Activities',
            'code': 'MCA-LP',
            'knec_code': '107',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Physical education, music, and arts'
        },
    ],
    
    'upper_primary': [
        {
            'name': 'English',
            'code': 'ENG-UP',
            'knec_code': '101',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'English language and literature'
        },
        {
            'name': 'Kiswahili',
            'code': 'KIS-UP',
            'knec_code': '102',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Kiswahili language and literature'
        },
        {
            'name': 'Mathematics',
            'code': 'MATH-UP',
            'knec_code': '103',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Mathematics'
        },
        {
            'name': 'Science and Technology',
            'code': 'SCI-UP',
            'knec_code': '104',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Science and technology'
        },
        {
            'name': 'Social Studies',
            'code': 'SOC-UP',
            'knec_code': '105',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Social studies and citizenship'
        },
        {
            'name': 'Religious Education',
            'code': 'RE-UP',
            'knec_code': '106',
            'is_compulsory': True,
            'is_religious_education': True,
            'religious_type': 'CRE',  # Default, can be changed
            'description': 'Religious education (CRE/IRE/HRE)'
        },
        {
            'name': 'Creative Arts',
            'code': 'ART-UP',
            'knec_code': '107',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Creative arts and music'
        },
        {
            'name': 'Physical and Health Education',
            'code': 'PHE-UP',
            'knec_code': '108',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Physical and health education'
        },
        {
            'name': 'Agriculture',
            'code': 'AGR-UP',
            'knec_code': '109',
            'is_compulsory': False,  # Optional in some schools
            'is_religious_education': False,
            'description': 'Agriculture'
        },
        {
            'name': 'Home Science',
            'code': 'HSC-UP',
            'knec_code': '110',
            'is_compulsory': False,  # Optional
            'is_religious_education': False,
            'description': 'Home science'
        },
    ],
    
    'junior_secondary': [
        {
            'name': 'English',
            'code': 'ENG-JS',
            'knec_code': '101',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'English language and literature'
        },
        {
            'name': 'Kiswahili',
            'code': 'KIS-JS',
            'knec_code': '102',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Kiswahili language and literature'
        },
        {
            'name': 'Mathematics',
            'code': 'MATH-JS',
            'knec_code': '103',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Mathematics'
        },
        {
            'name': 'Integrated Science',
            'code': 'SCI-JS',
            'knec_code': '104',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Integrated science'
        },
        {
            'name': 'Social Studies',
            'code': 'SOC-JS',
            'knec_code': '105',
            'is_compulsory': True,
            'is_religious_education': False,
            'description': 'Social studies'
        },
        {
            'name': 'Religious Education',
            'code': 'RE-JS',
            'knec_code': '106',
            'is_compulsory': True,
            'is_religious_education': True,
            'religious_type': 'CRE',  # Default, can be changed
            'description': 'Religious education (CRE/IRE/HRE)'
        },
        {
            'name': 'Business Studies',
            'code': 'BUS-JS',
            'knec_code': '111',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Business studies',
            'pathway_suggestions': ['stem', 'social_sciences']
        },
        {
            'name': 'Agriculture',
            'code': 'AGR-JS',
            'knec_code': '109',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Agriculture',
            'pathway_suggestions': ['stem', 'social_sciences']
        },
        {
            'name': 'Home Science',
            'code': 'HSC-JS',
            'knec_code': '110',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Home science',
            'pathway_suggestions': ['arts_sports', 'social_sciences']
        },
        {
            'name': 'Computer Studies',
            'code': 'COM-JS',
            'knec_code': '112',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Computer studies',
            'pathway_suggestions': ['stem']
        },
        {
            'name': 'Visual Arts',
            'code': 'ART-JS',
            'knec_code': '113',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Visual arts',
            'pathway_suggestions': ['arts_sports']
        },
        {
            'name': 'Performing Arts',
            'code': 'PER-JS',
            'knec_code': '114',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Performing arts (music, drama, dance)',
            'pathway_suggestions': ['arts_sports']
        },
        {
            'name': 'Physical Education',
            'code': 'PE-JS',
            'knec_code': '115',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Physical education and sports',
            'pathway_suggestions': ['arts_sports']
        },
        {
            'name': 'Pre-Technical Studies',
            'code': 'PRE-JS',
            'knec_code': '116',
            'is_compulsory': False,
            'is_religious_education': False,
            'description': 'Pre-technical studies',
            'pathway_suggestions': ['stem']
        },
    ],
}


def get_subjects_for_level(learning_level):
    """Get subject templates for a specific learning level"""
    return CBC_SUBJECT_TEMPLATES.get(learning_level, [])


def get_all_learning_levels():
    """Get all available learning levels"""
    return list(CBC_SUBJECT_TEMPLATES.keys())


def get_subject_by_name_and_level(name, learning_level):
    """Get a specific subject template by name and level"""
    subjects = get_subjects_for_level(learning_level)
    for subject in subjects:
        if subject['name'].lower() == name.lower():
            return subject
    return None


def get_applicable_grade_patterns(learning_level):
    """
    Get grade name patterns that apply to a learning level.
    Returns a list of patterns to match against grade names.
    """
    patterns = {
        'early_years': [
            'pre-primary 1', 'pre-primary 2', 'pre primary 1', 'pre primary 2',
            'pp1', 'pp2', 'pp 1', 'pp 2', 'pre-primary1', 'pre-primary2',
            'nursery', 'kindergarten', 'kg1', 'kg2'
        ],
        'lower_primary': [
            'grade 1', 'grade 2', 'grade 3', 'grade1', 'grade2', 'grade3',
            'g1', 'g2', 'g3', 'std 1', 'std 2', 'std 3', 'std1', 'std2', 'std3',
            'class 1', 'class 2', 'class 3', 'class1', 'class2', 'class3'
        ],
        'upper_primary': [
            'grade 4', 'grade 5', 'grade 6', 'grade4', 'grade5', 'grade6',
            'g4', 'g5', 'g6', 'std 4', 'std 5', 'std 6', 'std4', 'std5', 'std6',
            'class 4', 'class 5', 'class 6', 'class4', 'class5', 'class6'
        ],
        'junior_secondary': [
            'grade 7', 'grade 8', 'grade 9', 'grade7', 'grade8', 'grade9',
            'g7', 'g8', 'g9', 'std 7', 'std 8', 'std 9', 'std7', 'std8', 'std9',
            'form 1', 'form 2', 'form 3', 'form1', 'form2', 'form3',
            'class 7', 'class 8', 'class 9', 'class7', 'class8', 'class9'
        ],
    }
    return patterns.get(learning_level, [])


def filter_grades_by_learning_level(grades_queryset, learning_level):
    """
    Filter grades queryset to only include grades applicable to the learning level.
    Uses pattern matching on grade names (case-insensitive).
    """
    if not learning_level:
        return grades_queryset.none()
    
    patterns = get_applicable_grade_patterns(learning_level)
    if not patterns:
        return grades_queryset.none()
    
    from django.db.models import Q
    from functools import reduce
    import operator
    
    # Build Q objects for each pattern
    # Use case-insensitive contains for flexible matching
    q_objects = []
    for pattern in patterns:
        # Use icontains for flexible matching (handles variations like "Grade 1", "grade1", "GRADE 1")
        q_objects.append(Q(name__icontains=pattern))
    
    # Combine with OR
    if q_objects:
        combined_q = reduce(operator.or_, q_objects)
        return grades_queryset.filter(combined_q).distinct()
    
    return grades_queryset.none()



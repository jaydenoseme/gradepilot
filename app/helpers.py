def calculate_gpa(
    grades,
    gpa_scale='standard',
    grade_format='plus_minus',
    gpa_cap=4.0,
    weight_regular=0.0,
    weight_honors=0.0,
    weight_ap=0.0,
    weight_ib=0.0,
    weight_de=0.0,
    custom_gpa_map=None
):
    if not grades:
        return 0.0, [], []

    if custom_gpa_map is None:
        custom_gpa_map = {
            'A+': 4.0, 'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D+': 1.3, 'D': 1.0, 'D-': 0.7,
            'F': 0.0
        }

    sorted_grades = sorted(grades, key=lambda g: g.date)
    running_totals = []
    labels = []
    running_sum = 0
    count = 0

    for grade in sorted_grades:
        base = 0.0

        if hasattr(grade, 'letter') and grade.letter and grade_format == 'plus_minus':
            base = custom_gpa_map.get(grade.letter.upper(), 0.0)
        elif hasattr(grade, 'grade') and isinstance(grade.grade, (int, float)):
            if grade.grade >= 90:
                base = 4.0
            elif grade.grade >= 80:
                base = 3.0
            elif grade.grade >= 70:
                base = 2.0
            elif grade.grade >= 60:
                base = 1.0
            else:
                base = 0.0

        # Add course weight
        course_type = getattr(grade, 'course_type', 'Regular')
        weight = {
            'Regular': weight_regular,
            'Honors': weight_honors,
            'AP': weight_ap,
            'IB': weight_ib,
            'DE': weight_de
        }.get(course_type, 0.0)

        final_points = min(base + weight, gpa_cap)
        running_sum += final_points
        count += 1
        running_totals.append(round(running_sum / count, 2))

        try:
            label = grade.date.strftime('%b %-d %Y')
        except Exception:
            label = str(grade.date)
        labels.append(label)

    overall_gpa = round(running_sum / count, 2) if count else 0.0
    return overall_gpa, running_totals, labels

import random
import json
from pprint import pprint

def generate_student_data(num_students=30):
    """Generate random grades for students across 12 months."""
    # Student names
    first_names = ['Alex', 'Bailey', 'Casey', 'Dana', 'Eli', 'Fran', 'Gray', 'Harper',
                  'Indie', 'Jamie', 'Kai', 'Logan', 'Morgan', 'Nico', 'Ollie', 'Parker',
                  'Quinn', 'Reese', 'Sam', 'Taylor', 'Uma', 'Val', 'Winter', 'Xander',
                  'Yara', 'Zoe', 'Ash', 'Blake', 'Cameron', 'Devin']
    
    # Months abbreviations
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Possible grades
    grades = ['A', 'B', 'C', 'D', 'F']
    
    # Student-centric data structure
    student_data = {}
    
    # Generate data for each student
    for i in range(num_students):
        student_name = first_names[i]
        student_grades = {}
        
        # Generate grades for each month
        for month in months:
            # Randomly select a grade
            grade = random.choice(grades)
            student_grades[month] = grade
        
        # Add this student to the main data structure
        student_data[student_name] = student_grades
    
    return student_data

def reorganize_by_month(student_data):
    """Reorganize student data by month instead of by student."""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    month_data = {}
    
    # For each month, create a new dictionary with student:grade pairs
    for month in months:
        student_grades = {}
        
        # For each student, get their grade for this month
        for student, grades in student_data.items():
            student_grades[student] = grades[month]
        
        # Add this month's data to the main structure
        month_data[month] = student_grades
    
    return month_data

def main():
    # Generate student data
    student_data = generate_student_data()
    
    # Print the original student-centric data
    print("ORIGINAL DATA (ORGANIZED BY STUDENT):")
    print("=====================================")
    pprint(student_data, sort_dicts=False, width=80)
    print("\n")
    
    # Reorganize the data by month
    month_data = reorganize_by_month(student_data)
    
    # Print the reorganized month-centric data
    print("REORGANIZED DATA (ORGANIZED BY MONTH):")
    print("======================================")
    pprint(month_data, sort_dicts=False, width=80)

if __name__ == "__main__":
    main()
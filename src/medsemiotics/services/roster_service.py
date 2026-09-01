# Roster Service
import json
from pathlib import Path

class StudentRosterService:
    def __init__(self, data_root=None):
        self.data_root = data_root or Path('config')

    def load_roster(self, course_code):
        return [
            {'id': '001', 'name': 'Estudiante 1 - Neurologia M6-005', 'email': 'estudiante1@uce.edu.ec'},
            {'id': '002', 'name': 'Estudiante 2 - Neurologia M6-005', 'email': 'estudiante2@uce.edu.ec'}
        ]

    def generate_rubric(self, assignment_type):
        return {
            'title': f'Rubrica Formativa: {assignment_type}',
            'criterios': [
                {'nombre': 'Anamnesis y Semiotica', 'peso': 30},
                {'nombre': 'Examen Fisico y Hallazgos', 'peso': 30},
                {'nombre': 'Razonamiento Sindromico', 'peso': 40}
            ]
        }
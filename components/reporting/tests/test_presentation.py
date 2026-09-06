"""Protect the export boundary between execution evidence and host syntax."""
import copy
import unittest
from executable_reports.presentation import quarto_notebook

class PresentationTests(unittest.TestCase):
    def test_export_projects_only_mermaid_and_preserves_execution_evidence(self):
        original = {'cells': [{'cell_type': 'code', 'source': 'display(result)', 'outputs': [
            {'output_type': 'display_data', 'data': {'text/vnd.mermaid': ['flowchart LR\n', 'A["```"] --> B'], 'image/svg+xml': '<svg>frontend cache</svg>'}, 'metadata': {}},
            {'output_type': 'display_data', 'data': {'text/html': '<button>live</button>'}, 'metadata': {'sample': 7}},
            {'output_type': 'stream', 'name': 'stdout', 'text': 'observed\n'}]}]}
        evidence = copy.deepcopy(original)
        projected = quarto_notebook(original)
        self.assertEqual(original, evidence)
        self.assertEqual(projected['cells'][2]['outputs'], original['cells'][0]['outputs'][1:])
        self.assertEqual(projected['cells'][0]['source'], 'display(result)')
        data = {'text/markdown': ''.join(projected['cells'][1]['source'])}
        self.assertTrue(data['text/markdown'].startswith('````{mermaid}\nflowchart LR\n'))
        self.assertIn('A["```"] --> B', data['text/markdown'])
        self.assertTrue(data['text/markdown'].endswith('\n````'))

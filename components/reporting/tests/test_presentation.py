"""Protect the export boundary between execution evidence and host syntax."""
import copy
import unittest
from executable_reports.presentation import Mermaid, quarto_notebook

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

    def test_mermaid_compact_form_drops_styling_and_prefers_a_supplied_summary(self):
        source = 'flowchart TB\naccTitle: T\n  a["read<br/>x #61; 1"]:::file --> b\n  classDef file fill:#fff'
        plain = Mermaid(source)._repr_mimebundle_()["text/plain"]
        self.assertEqual(plain, 'flowchart TB\n  a["read · x = 1"] --> b')
        class Summarized(str):
            compact = "2 steps"
        self.assertEqual(Mermaid(Summarized(source))._repr_mimebundle_()["text/plain"], "2 steps")
        self.assertEqual(Mermaid(source, text="own")._repr_mimebundle_(), {"text/vnd.mermaid": source, "text/plain": "own"})

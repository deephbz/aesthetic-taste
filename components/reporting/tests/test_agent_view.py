"""The agent view reads compact forms and flags outputs that lack one."""
import unittest

from executable_reports.agent_view import agent_view


class AgentViewTests(unittest.TestCase):
    def test_reads_compact_forms_and_flags_rich_only_outputs(self):
        notebook = {'cells': [
            {'cell_type': 'markdown', 'source': ['# Result\n', 'Markout is positive.']},
            {'cell_type': 'code', 'id': 'cell-a', 'source': 'store', 'outputs': [
                {'output_type': 'display_data', 'metadata': {},
                 'data': {'text/html': '<table>' + 'x' * 5000 + '</table>', 'text/plain': 'cache miss markout'}},
                {'output_type': 'display_data', 'metadata': {}, 'data': {'image/png': 'iVBOR' * 100}},
                {'output_type': 'stream', 'name': 'stdout', 'text': 'y' * 50}]}]}
        view = agent_view(notebook, limit=20)
        # The HTML form is for the human; the agent must not pay for it.
        self.assertNotIn('<table>', view)
        self.assertIn('[cell-a#0] text/html, text/plain', view)
        self.assertIn('    cache miss markout', view)
        # A producer without a compact form is visible as such, not silently dropped.
        self.assertIn('[image/png; no compact form]', view)
        self.assertIn('… [cut at 20 of 50 characters]', view)
        self.assertTrue(view.startswith('# Result\nMarkout is positive.'))
        self.assertNotIn('store', agent_view(notebook).split('[cell-a#0]')[0])
        self.assertIn('[cell-a] code\n    store', agent_view(notebook, code=True))


if __name__ == '__main__':
    unittest.main()

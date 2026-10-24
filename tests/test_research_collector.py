import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import research_collector as collector


class ResearchCollectorTests(unittest.TestCase):
    def test_failed_run_never_reads_committed_output(self):
        with patch.object(collector.subprocess, 'run', return_value=subprocess.CompletedProcess([], 3)):
            result = collector.collect('Netflix', 'MA')
        self.assertEqual(result['ads'], [])
        self.assertEqual(result['status'], 'failed')

    def test_new_output_includes_search_provenance_without_fake_spend(self):
        def run(cmd, **kwargs):
            output = Path(cmd[cmd.index('--out') + 1])
            output.write_text(json.dumps([{'ad_id': '123', 'body': 'Netflix abonnement', 'days_shown': 45}]), encoding='utf-8')
            return subprocess.CompletedProcess(cmd, 0)
        with patch.object(collector.subprocess, 'run', side_effect=run):
            ad = collector.collect('compte Netflix Maroc', 'MA', 'Netflix')['ads'][0]
        self.assertEqual(ad['brand'], 'Netflix')
        self.assertEqual(ad['searchQuery'], 'compte Netflix Maroc')
        self.assertEqual(ad['countries'], ['MA'])
        self.assertEqual(ad['spend'], '')
        self.assertEqual(ad['daysRunning'], 45)

    def test_empty_run_is_distinct_from_failure(self):
        with patch.object(collector.subprocess, 'run', return_value=subprocess.CompletedProcess([], 4)):
            result = collector.collect('Spotify', 'MA')
        self.assertEqual(result, {'ads': [], 'status': 'empty'})


if __name__ == '__main__':
    unittest.main()

"""Тесты сборки читалки (только стандартная библиотека).

Запуск из корня репозитория:  python -m unittest discover -s tests
"""
import json, os, re, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "build_html.py")
DEMO = os.path.join(ROOT, "demo", "Основы Python")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_html  # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding="utf-8", env=ENV)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def embedded_data(page):
    m = re.search(r'<script type="application/json" id="uk-data">(.*?)</script>', page, re.S)
    return json.loads(m.group(1))


class BuildDemo(unittest.TestCase):
    def test_demo_builds_single_offline_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "demo.html")
            r = run(DEMO, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            page = read(out)
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("<title>Основы Python</title>", page)
        self.assertNotIn("__DATA__", page)
        data = embedded_data(page)
        self.assertFalse(data["webfonts"])  # по умолчанию никаких внешних запросов
        subj = data["subjects"][0]
        self.assertEqual(len(subj["questions"]), 5)
        self.assertEqual(subj["course"], "демонстрационный курс, 1 семестр")
        self.assertEqual(len(subj["tests"]), 1)
        self.assertEqual(len(subj["dates"]), 3)
        q1 = subj["questions"][0]
        self.assertEqual(q1["n"], 1)
        self.assertTrue(q1["short"] and q1["full"] and q1["plan"] and q1["qa"])
        self.assertIn("<pre><code>", subj["questions"][2]["full"])  # блок кода в вопросе 3

    def test_webfonts_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "demo.html")
            run(DEMO, "--out", out, "--webfonts")
            self.assertTrue(embedded_data(read(out))["webfonts"])

    def test_check_mode_is_clean_and_writes_nothing(self):
        r = run(DEMO, "--check", "--min-full", "1500")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("вопросов 5", r.stdout)
        self.assertIn("вопросов с замечаниями: 0", r.stdout)


class Markdown(unittest.TestCase):
    def test_inline_and_escape(self):
        self.assertEqual(build_html.inline("**жирный** и `a<b`"), "<strong>жирный</strong> и <code>a&lt;b</code>")

    def test_code_block(self):
        h = build_html.md("Текст\n\n```\nif x < 1:\n    pass\n```\n")
        self.assertIn("<pre><code>if x &lt; 1:\n    pass</code></pre>", h)

    def test_sentences_ignore_abbreviations(self):
        s = build_html.split_sentences("Это было в 1991 г. на конференции. Потом вышла версия 3.0. Конец.")
        self.assertEqual(len(s), 3)

    def test_date_sort_key(self):
        self.assertLess(build_html.date_key("XIX в."), build_html.date_key("1991"))
        self.assertLess(build_html.date_key("100 до Р. Х."), 0)


if __name__ == "__main__":
    unittest.main()

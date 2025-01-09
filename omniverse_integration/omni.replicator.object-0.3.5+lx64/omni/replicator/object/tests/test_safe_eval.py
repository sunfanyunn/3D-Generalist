# unit test
if __name__ == "__main__":
    import unittest as ut
    import math

    import sys
    sys.path.append('../utility/')
    sys._UNIT_TEST = True

    from safe_eval import safe_eval, _flatten

    class TestFlatten(ut.TestCase):
        def test_valid_iterables(self):
            for (test_iterable, flattened) in [
                ({'1':2, 'z':4}, [('1',2),('z',4)]),
                ([('x',2), ('y',4)], [('x',2), ('y',4)]),
                (('None',None), [('None', None)]),
                ({'x':2, 'y':None}, [('x',2), ('y',None)]),
                ([('x',2),{'y':3,'z':5}, ((('p',6),('a',5)), ('s',100))],  [('x',2),('y',3),('z',5),('p',6),('a',5),('s',100)]),
                ([[({'x':2}, {'y':{'x':1}})], ({'1':2, 'z':4}, ('p',90))], [('x',2),('y',{'x':1}),('1',2),('z',4),('p',90)] ),
                ((((((((({'x':2}))))), ('y',3)))), [('x',2), ('y',3)] )
            ]:
                self.assertEqual(list(_flatten(test_iterable)),
                                flattened)

    class TestSafeEval(ut.TestCase):
        def test_literals(self):
            self.assertEqual(safe_eval("7"), 7)
            self.assertEqual(safe_eval("+6"), 6)
            self.assertEqual(safe_eval("--+-7"), -7)
            self.assertEqual(safe_eval("None", {"extra" : None}), None)

        def test_arithmetic_expressions(self):
            # simple
            self.assertEqual(safe_eval("123 + 123 // 32 ** 21"), 123)
            self.assertEqual(safe_eval("camera + seed", {"camera": 123, "seed": 12}), 135)
            self.assertEqual(safe_eval("(56 + 59.2//58 )/23"), 57/23)

            # math
            self.assertEqual(safe_eval("math.sin(a) + math.cos(b) - math.pow(1,2)", {'a' : 123, 'b' : 321 }),
                             math.sin(123) + math.cos(321) - math.pow(1,2))
            self.assertEqual(safe_eval("123 ** math.sin(math.cos(a))", {'a' : 56}),
                             123 ** math.sin(math.cos(56)))
            self.assertEqual(safe_eval("g ** math.sin(math.cos(a+b)) // math.pi",
                                       ([{'a':2,'b':3}, {'c':4}, (('d',5), {'e':7}, [('f',8)])], ('g', 123)) ),
                             123 ** math.sin(math.cos(5) // math.pi))

        def test_other_expressions(self):
            self.assertEqual(safe_eval("seed", {"seed" : 123}), 123)
            self.assertEqual(safe_eval("30 % int(20.3412)"), 30 % 20)
            self.assertEqual(safe_eval("str(5)"), "5")
            self.assertEqual(safe_eval("len([12,3])"), 2)
            self.assertEqual(safe_eval("(5//len([2]) + int(any([True, False])))"), 6)
            self.assertEqual(safe_eval("i if i <= 5 else i % 5", {"i" : 100}), 0)
            self.assertEqual(safe_eval("bool(j if j+i <= 5 else i if j < 5 else 1)", {"i":1, "j":5}), True)
            self.assertEqual(safe_eval("arr[:]", {"arr":[213,41]}), [213,41])
            self.assertEqual(safe_eval("arr[0]+1", {"arr":[1,1,1]}), 2)

        def test_illegal_expressions(self):
            with self.assertRaises(Exception):
                safe_eval("arr[20000]+1", {"arr":[1,1,1]})
            with self.assertRaises(Exception):
                safe_eval("x=7")
            with self.assertRaises(Exception):
                safe_eval("1/0")
            with self.assertRaises(Exception):
                safe_eval("x")

            with self.assertRaises(Exception):
                safe_eval("print(\"123\")")
            with self.assertRaises(Exception):
                safe_eval("yield None")
            with self.assertRaises(Exception):
                safe_eval("try: 2/0\nexcept: exit(1)")
            with self.assertRaises(Exception):
                safe_eval("for x in range(0, 1000): x-=1")
            with self.assertRaises(Exception):
                safe_eval("class X: pass")
            with self.assertRaises(Exception):
                safe_eval("raise Exception(\"123\")")
            with self.assertRaises(Exception):
                safe_eval("assert(False)")
            with self.assertRaises(Exception):
                safe_eval("math.pi(12)")
            with self.assertRaises(Exception):
                safe_eval("any(i % 5 == i % 3 for i in range(10))")
            with self.assertRaises(Exception):
                safe_eval("return 42 if a == 1 else None", {"a":1})
            with self.assertRaises(Exception):
                safe_eval("with open('t.txt', 'w+') as f: f.write(\" 123\")")
            with self.assertRaises(Exception):
                safe_eval("def f(): raise(\"error\"); f()")
            with self.assertRaises(Exception):
                safe_eval("(lambda x : x)(1)")
            with self.assertRaises(Exception):
                safe_eval("import os")
            with self.assertRaises(Exception):
                safe_eval("list.append = lambda self, item: None")
            with self.assertRaises(Exception):
                safe_eval("123 + 123; import os; os.system('sudo rm -rf /')")
            with self.assertRaises(Exception):
                safe_eval("open('test.txt', 'w').write('Hello')")
            with self.assertRaises(Exception):
                safe_eval("exit(0)")
            with self.assertRaises(Exception):
                safe_eval("f(5)", {"f": lambda x: x + 2})
            with self.assertRaises(Exception):
                safe_eval("f(5)", {"f": lambda x: print(x)})
            with self.assertRaises(Exception):
                safe_eval("while True: math.cos(1)")
            with self.assertRaises(Exception):
                safe_eval("__import__('os').system('dir')")
            with self.assertRaises(Exception):
                safe_eval("print((1).__class__.__bases__[0].__subclasses__())")
            with self.assertRaises(Exception):
                safe_eval("(__import__('types').FunctionType).__code__")
            with self.assertRaises(Exception):
                safe_eval("import os; math.cos = lambda x:os.system('sudo rm -rf /')")

    ut.main()
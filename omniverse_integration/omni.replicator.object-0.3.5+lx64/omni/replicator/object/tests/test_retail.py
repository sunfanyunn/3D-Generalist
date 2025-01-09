# NOTE:
#   omni.kit.test - std python's unittest module with additional wrapping to add suport for async/await tests
#   For most things refer to unittest docs: https://docs.python.org/3/library/unittest.html
import omni.kit.test

# Extnsion for writing UI tests (simulate UI interaction)
import omni.kit.ui_test as ui_test

# Import extension python module we are testing with absolute import path, as if we are external user (other extension)
import omni.replicator.object

import os

# Having a test class dervived from omni.kit.test.AsyncTestCase declared on the root of module will make it auto-discoverable by omni.kit.test
class Test(omni.kit.test.AsyncTestCase):
    # Before running each test
    async def setUp(self):
        pass

    # After running each test
    async def tearDown(self):
        pass

    # Actual test, notice it is "async" function, so "await" can be used if needed
    async def test_hello_public_function(self):
        print('test_hello_public_function')
        #
        try:
            await omni.replicator.object.new_stage_async()
            await omni.replicator.object.wait_frames()
            await omni.replicator.object.on_simulate(self, os.path.abspath(f"{os.path.dirname(__file__)}/../configs/unittest_config.yaml"), True)

            #files = os.listdir('/tmp/unittest_output/images')
            #self.assertEqual( len(files), 2)

        except Exception as e:
            raise Exception(f'Something is wrong: {str(e)}.')

        #result = omni.replicator.object.some_public_function(4)
        #self.assertEqual(result, 256)


    # async def test_window_button(self):


    #     # Find a label in our window
    #     label = ui_test.find("My Window//Frame/**/Label[*]")

    #     # Find buttons in our window
    #     add_button = ui_test.find("My Window//Frame/**/Button[*].text=='Add'")
    #     reset_button = ui_test.find("My Window//Frame/**/Button[*].text=='Reset'")

    #     # Click reset button
    #     await reset_button.click()
    #     self.assertEqual(label.widget.text, "empty")

    #     await add_button.click()
    #     self.assertEqual(label.widget.text, "count: 1")

    #     await add_button.click()
    #     self.assertEqual(label.widget.text, "count: 2")

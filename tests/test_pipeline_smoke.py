from aidocsynth.controllers.main_controller import MainController
def test_pipeline(tmp_path):
    f = tmp_path/"d.txt"; f.write_text("x")
    MainController().handle_drop([str(f)])

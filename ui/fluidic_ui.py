async def launch_ui(environment):
    try:
        from kivy.app import App
        from kivy.uix.label import Label
    except Exception:
        print("Kivy not installed. Running console UI.")
        print("Umer OS UI active.")
        return

    class UmerApp(App):
        def build(self):
            return Label(text="Umer OS")

    UmerApp().run()
    
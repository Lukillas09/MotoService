from config.version import APP_VERSION


def app_version(_request):
    return {"app_version": APP_VERSION}

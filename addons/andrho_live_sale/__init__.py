from . import models


def post_init_hook(env):
    env["andrho.live.sale"].andrho_set_enabled(True)

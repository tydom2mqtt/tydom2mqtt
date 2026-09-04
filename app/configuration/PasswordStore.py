import logging
import os
import stat

logger = logging.getLogger(__name__)

PASSWORD_FILENAME = "tydom_local_password"


class PasswordStore:
    """Persist the gateway's local password outside of the configuration.

    A Tydom hub hands out its local password only during the window that
    follows a press on its physical button. Storing the discovered value lets
    the app reconnect on its own afterwards, so the password never has to be
    written into the add-on options, a compose file or an environment
    variable.

    In a Home Assistant add-on /data is persistent, so this is transparent.
    Under plain `docker run` it is not, unless a volume is mounted: the path
    actually used is logged on every write so a non-persistent setup is
    obvious immediately rather than discovered weeks later.
    """

    def __init__(self, directory):
        self.directory = directory
        self.path = os.path.join(directory, PASSWORD_FILENAME)

    def read(self):
        """Return the stored password, or None when there is nothing usable."""
        try:
            with open(self.path) as stored:
                password = stored.read().strip()
        except FileNotFoundError:
            return None
        except OSError as e:
            logger.warning("Cannot read the stored Tydom password (%s)", e)
            return None

        if password == "":
            return None

        logger.info("Using the Tydom local password stored in %s", self.path)
        return password

    def write(self, password):
        """Store the password, readable by its owner only.

        Returns True when the value was persisted. A failure is not fatal:
        the app can still run with the password it just discovered, it will
        simply need the button again on the next start.
        """
        try:
            os.makedirs(self.directory, exist_ok=True)
            with open(self.path, "w") as stored:
                stored.write(password)
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            logger.warning(
                "Could not store the Tydom local password in %s (%s). "
                "The hub's button will be needed again on the next start.",
                self.path,
                e,
            )
            return False

        logger.info("Tydom local password stored in %s", self.path)
        return True

    def clear(self):
        """Forget the stored password, so pairing starts over."""
        try:
            os.remove(self.path)
            logger.info("Discarded the stored Tydom local password (%s)", self.path)
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning("Could not discard %s (%s)", self.path, e)

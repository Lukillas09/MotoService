from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase

from apps.clientes.models import Cliente
from apps.motos.models import Moto
from apps.servicios.models import Servicio


@skipUnless(
    connection.vendor == "postgresql",
    "Requiere PostgreSQL real: SQLite no implementa locks de select_for_update.",
)
class ServicioConcurrencyPostgreSQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre="Carlos")
        self.moto = Moto.objects.create(
            cliente=self.cliente,
            marca="Honda",
            modelo="Wave",
            kilometraje_actual=10000,
        )

    def _archivar_y_esperar(self, modelo, pk, bloqueado, liberar):
        close_old_connections()
        try:
            with transaction.atomic():
                objeto = modelo.objects.select_for_update(no_key=True).get(pk=pk)
                objeto.activo = False
                objeto.save(update_fields=("activo", "actualizado_en"))
                bloqueado.set()
                if not liberar.wait(timeout=10):
                    raise TimeoutError("No se liberó la transacción de archivado.")
        finally:
            connection.close()

    def _publicar_pid(self, cola_pid):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            cola_pid.put(cursor.fetchone()[0])

    def _esperar_bloqueo(self, pid):
        limite = monotonic() + 10
        while monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT wait_event_type, pg_blocking_pids(%s) "
                    "FROM pg_stat_activity WHERE pid = %s",
                    (pid, pid),
                )
                fila = cursor.fetchone()
            if fila and fila[0] == "Lock" and fila[1]:
                return
            sleep(0.02)
        self.fail(f"El backend PostgreSQL {pid} no esperó el lock previsto.")

    def _crear_servicio(self, cola_pid):
        close_old_connections()
        try:
            self._publicar_pid(cola_pid)
            try:
                Servicio.objects.create(moto_id=self.moto.pk)
            except ValidationError as error:
                mensajes = error.message_dict.get("moto", ())
                return any("archivad" in mensaje.lower() for mensaje in mensajes)
            return False
        finally:
            connection.close()

    def _crear_moto(self, cola_pid):
        close_old_connections()
        try:
            self._publicar_pid(cola_pid)
            try:
                Moto.objects.create(
                    cliente_id=self.cliente.pk,
                    marca="Yamaha",
                    modelo="Crypton",
                )
            except ValidationError as error:
                return "cliente" in error.message_dict
            return False
        finally:
            connection.close()

    def _verificar_archivado_gana_a_servicio(self, modelo, pk):
        bloqueado = Event()
        liberar = Event()
        cola_pid = Queue()
        servicio = None

        with ThreadPoolExecutor(max_workers=2) as executor:
            archivado = executor.submit(
                self._archivar_y_esperar,
                modelo,
                pk,
                bloqueado,
                liberar,
            )
            try:
                self.assertTrue(bloqueado.wait(timeout=10))
                servicio = executor.submit(self._crear_servicio, cola_pid)
                self._esperar_bloqueo(cola_pid.get(timeout=10))
            finally:
                liberar.set()

            archivado.result(timeout=10)
            self.assertIsNotNone(servicio)
            self.assertTrue(servicio.result(timeout=10))

        self.assertFalse(Servicio.objects.exists())

    def test_no_crea_servicio_si_archivado_cliente_gana_la_carrera(self):
        self._verificar_archivado_gana_a_servicio(Cliente, self.cliente.pk)

    def test_no_crea_servicio_si_archivado_moto_gana_la_carrera(self):
        self._verificar_archivado_gana_a_servicio(Moto, self.moto.pk)

    def test_no_crea_moto_si_archivado_cliente_gana_la_carrera(self):
        bloqueado = Event()
        liberar = Event()
        cola_pid = Queue()
        alta = None

        with ThreadPoolExecutor(max_workers=2) as executor:
            archivado = executor.submit(
                self._archivar_y_esperar,
                Cliente,
                self.cliente.pk,
                bloqueado,
                liberar,
            )
            try:
                self.assertTrue(bloqueado.wait(timeout=10))
                alta = executor.submit(self._crear_moto, cola_pid)
                self._esperar_bloqueo(cola_pid.get(timeout=10))
            finally:
                liberar.set()

            archivado.result(timeout=10)
            self.assertIsNotNone(alta)
            self.assertTrue(alta.result(timeout=10))

        self.assertFalse(Moto.objects.exclude(pk=self.moto.pk).exists())

    def test_servicios_concurrentes_conservan_kilometraje_maximo(self):
        barrera = Barrier(2)

        def registrar(kilometraje):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                Servicio.objects.create(
                    moto_id=self.moto.pk,
                    kilometraje=kilometraje,
                )
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futuros = (
                executor.submit(registrar, 12000),
                executor.submit(registrar, 15000),
            )
            for futuro in futuros:
                futuro.result(timeout=10)

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 15000)
        self.assertEqual(Servicio.objects.count(), 2)

    def test_guardado_obsoleto_no_reduce_kilometraje_concurrente(self):
        instancia_obsoleta = Moto.objects.get(pk=self.moto.pk)
        bloqueado = Event()
        liberar = Event()
        cola_pid = Queue()

        def actualizar_y_esperar():
            close_old_connections()
            try:
                with transaction.atomic():
                    moto = Moto.objects.select_for_update(no_key=True).get(
                        pk=self.moto.pk
                    )
                    Moto.objects.filter(pk=moto.pk).update(kilometraje_actual=15000)
                    bloqueado.set()
                    if not liberar.wait(timeout=10):
                        raise TimeoutError("No se liberó la actualización de kilometraje.")
            finally:
                connection.close()

        def guardar_obsoleto():
            close_old_connections()
            try:
                self._publicar_pid(cola_pid)
                instancia_obsoleta.kilometraje_actual = 12000
                try:
                    instancia_obsoleta.save()
                except ValidationError as error:
                    return "kilometraje_actual" in error.message_dict
                return False
            finally:
                connection.close()

        guardado = None
        with ThreadPoolExecutor(max_workers=2) as executor:
            actualizacion = executor.submit(actualizar_y_esperar)
            try:
                self.assertTrue(bloqueado.wait(timeout=10))
                guardado = executor.submit(guardar_obsoleto)
                self._esperar_bloqueo(cola_pid.get(timeout=10))
            finally:
                liberar.set()

            actualizacion.result(timeout=10)
            self.assertIsNotNone(guardado)
            self.assertTrue(guardado.result(timeout=10))

        self.moto.refresh_from_db()
        self.assertEqual(self.moto.kilometraje_actual, 15000)

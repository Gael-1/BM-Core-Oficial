from django.core.management.base import BaseCommand

from inventory import alertas


class Command(BaseCommand):
    help = "Envía por correo los productos con stock bajo que aún no se han avisado (pensado para un cron diario)."

    def add_arguments(self, parser):
        parser.add_argument("--todos", action="store_true", help="Reenvía también los ya avisados.")

    def handle(self, *args, **opciones):
        enviados = alertas.enviar_pendientes(todos=opciones["todos"])
        if enviados:
            self.stdout.write(self.style.SUCCESS(f"Aviso enviado con {enviados} producto(s)."))
        else:
            self.stdout.write("No hay avisos pendientes.")

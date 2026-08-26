from datetime import date, time
from decimal import Decimal

from django.test import TestCase

from .forms import FuncionarioForm
from .models import ConfiguracionGeneral, Empresa, Funcionario, Sucursal, Turno


class FuncionarioConfiguracionFormTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa A", ruc="8001")
        self.otra_empresa = Empresa.objects.create(nombre="Empresa B", ruc="8002")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, nombre="Casa Central")
        self.sucursal_inactiva = Sucursal.objects.create(
            empresa=self.empresa,
            nombre="Sucursal histórica",
            activo=False,
        )
        self.otra_sucursal = Sucursal.objects.create(empresa=self.otra_empresa, nombre="Otra sucursal")
        self.turno = Turno.objects.create(
            empresa=self.empresa,
            nombre="Turno Día",
            hora_entrada=time(8, 0),
            hora_salida=time(17, 0),
            activo=True,
        )
        self.otra_turno = Turno.objects.create(
            empresa=self.otra_empresa,
            nombre="Turno B",
            hora_entrada=time(8, 0),
            hora_salida=time(17, 0),
            activo=True,
        )
        self.config = ConfiguracionGeneral.obtener()
        self.config.bancos_personalizados = "Banco Test"
        self.config.cargos_personalizados = "Cargo Test"
        self.config.sectores_personalizados = "Sector Test"
        self.config.salario_base_default = Decimal("2899048.00")
        self.config.porcentaje_limite_deuda_default = Decimal("30.00")
        self.config.save()

    def _post_data(self, funcionario=None, **overrides):
        data = {
            "nombre": "Ana",
            "apellido": "Gomez",
            "cedula": "1234567",
            "turno": str(self.turno.id),
            "empresa": str(self.empresa.id),
            "sucursal_rel": str(self.sucursal.id),
            "cargo": "Cargo Test",
            "sector": "Sector Test",
            "ips": "on",
            "bono": "500000",
            "modalidad_cobro": Funcionario.ModalidadesCobro.TRANSFERENCIA,
            "banco": "Banco Test",
            "tipo_cuenta": Funcionario.TiposCuenta.AHORRO,
            "numero_cuenta": "001122",
            "fecha_ingreso": "2026-01-15",
            "direccion": "Av. Siempre Viva",
            "ciudad": "Asunción",
            "departamento": "Central",
            "telefono": "0981000000",
            "correo": "ana@example.com",
            "fecha_nacimiento": "1990-05-20",
            "nacionalidad": "Paraguaya",
            "estado_civil": "Soltera",
            "contacto_emergencia_nombre": "Juan Gomez",
            "contacto_emergencia_parentesco": "Padre",
            "contacto_emergencia_telefono": "0981111111",
            "tipo_sangre": "O+",
            "alergias": "Ninguna",
            "enfermedad_importante": "",
            "medicacion_actual": "",
            "seguro_medico": "",
            "activo": "on",
        }
        if funcionario:
            data["cedula"] = funcionario.cedula
        data.update(overrides)
        return data

    def test_date_inputs_render_existing_values_in_browser_format(self):
        funcionario = Funcionario.objects.create(
            nombre="Ana",
            apellido="Gomez",
            cedula="1234567",
            sucursal_rel=self.sucursal,
            turno=self.turno,
            fecha_ingreso=date(2026, 1, 15),
            fecha_nacimiento=date(1990, 5, 20),
        )

        form = FuncionarioForm(instance=funcionario, empresa_activa=self.empresa)

        self.assertIn('value="2026-01-15"', str(form["fecha_ingreso"]))
        self.assertIn('value="1990-05-20"', str(form["fecha_nacimiento"]))

    def test_catalogs_from_configuration_are_used_by_funcionario_form(self):
        form = FuncionarioForm(empresa_activa=self.empresa)

        self.assertIn(("Banco Test", "Banco Test"), form.fields["banco"].choices)
        self.assertIn(("Cargo Test", "Cargo Test"), form.fields["cargo"].choices)
        self.assertIn(("Sector Test", "Sector Test"), form.fields["sector"].choices)

    def test_edit_preserves_existing_values_and_salary_when_unrelated_field_changes(self):
        funcionario = Funcionario.objects.create(
            nombre="Ana",
            apellido="Gomez",
            cedula="1234567",
            sucursal_rel=self.sucursal,
            turno=self.turno,
            cargo="Cargo Test",
            sector="Sector Test",
            ips=True,
            salario_base=Decimal("3600000.00"),
            porcentaje_limite_deuda=Decimal("25.00"),
            bono=Decimal("500000.00"),
            modalidad_cobro=Funcionario.ModalidadesCobro.TRANSFERENCIA,
            banco="Banco Test",
            tipo_cuenta=Funcionario.TiposCuenta.AHORRO,
            numero_cuenta="001122",
            fecha_ingreso=date(2026, 1, 15),
            fecha_nacimiento=date(1990, 5, 20),
        )

        form = FuncionarioForm(
            data=self._post_data(funcionario, telefono="0999999999"),
            instance=funcionario,
            empresa_activa=self.empresa,
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())
        editado = form.save()
        editado.refresh_from_db()

        self.assertEqual(editado.fecha_ingreso, date(2026, 1, 15))
        self.assertEqual(editado.fecha_nacimiento, date(1990, 5, 20))
        self.assertEqual(editado.salario_base, Decimal("3600000.00"))
        self.assertEqual(editado.porcentaje_limite_deuda, Decimal("25.00"))
        self.assertEqual(editado.bono, Decimal("500000.00"))
        self.assertEqual(editado.banco, "Banco Test")
        self.assertEqual(editado.telefono, "0999999999")

    def test_current_catalog_values_and_inactive_branch_remain_valid_on_edit(self):
        funcionario = Funcionario.objects.create(
            nombre="Ana",
            apellido="Gomez",
            cedula="1234567",
            sucursal_rel=self.sucursal_inactiva,
            turno=self.turno,
            cargo="Cargo Histórico",
            sector="Sector Histórico",
            banco="Banco Histórico",
            modalidad_cobro=Funcionario.ModalidadesCobro.TRANSFERENCIA,
            tipo_cuenta=Funcionario.TiposCuenta.AHORRO,
            numero_cuenta="001122",
        )

        form = FuncionarioForm(instance=funcionario, empresa_activa=self.empresa)

        self.assertIn(("Cargo Histórico", "Cargo Histórico (valor actual)"), form.fields["cargo"].choices)
        self.assertIn(("Sector Histórico", "Sector Histórico (valor actual)"), form.fields["sector"].choices)
        self.assertIn(("Banco Histórico", "Banco Histórico (valor actual)"), form.fields["banco"].choices)
        self.assertIn(self.sucursal_inactiva, list(form.fields["sucursal_rel"].queryset))

    def test_empresa_activa_filters_turnos_sucursales_and_empresas(self):
        form = FuncionarioForm(empresa_activa=self.empresa)

        self.assertIn(self.empresa, list(form.fields["empresa"].queryset))
        self.assertNotIn(self.otra_empresa, list(form.fields["empresa"].queryset))
        self.assertIn(self.turno, list(form.fields["turno"].queryset))
        self.assertNotIn(self.otra_turno, list(form.fields["turno"].queryset))

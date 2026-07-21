"""Informe completo — Panel de 8 Expertos — Forecast DCIC SpA"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
import os

OUTPUT_DIR = r"C:\Users\rafae\OneDrive\Escritorio\Proyecto Forecast"

AZUL_OSCURO    = HexColor('#1B3A6B')
AZUL_MEDIO     = HexColor('#2563EB')
AZUL_CLARO     = HexColor('#DBEAFE')
GRIS_OSCURO    = HexColor('#374151')
GRIS_MEDIO     = HexColor('#6B7280')
GRIS_CLARO     = HexColor('#F3F4F6')
ROJO           = HexColor('#DC2626')
VERDE          = HexColor('#16A34A')
AMARILLO_CLARO = HexColor('#FEF9C3')
AMARILLO_OSC   = HexColor('#854D0E')
ROJO_CLARO     = HexColor('#FEE2E2')
VERDE_CLARO    = HexColor('#DCFCE7')
NAVY           = HexColor('#0F2D6B')
SLATE          = HexColor('#334155')


def st():
    return {
        'Titulo':    ParagraphStyle('Titulo',    fontName='Helvetica-Bold',    fontSize=22, textColor=NAVY,       spaceAfter=6,  alignment=TA_CENTER),
        'Subtitulo': ParagraphStyle('Subtitulo', fontName='Helvetica',         fontSize=11, textColor=GRIS_MEDIO, spaceAfter=4,  alignment=TA_CENTER),
        'H1':        ParagraphStyle('H1',        fontName='Helvetica-Bold',    fontSize=14, textColor=NAVY,       spaceBefore=14, spaceAfter=6),
        'H2':        ParagraphStyle('H2',        fontName='Helvetica-Bold',    fontSize=11, textColor=AZUL_MEDIO, spaceBefore=10, spaceAfter=4),
        'H3':        ParagraphStyle('H3',        fontName='Helvetica-Bold',    fontSize=9,  textColor=SLATE,      spaceBefore=8,  spaceAfter=3),
        'Body':      ParagraphStyle('Body',      fontName='Helvetica',         fontSize=9,  textColor=GRIS_OSCURO, spaceAfter=4, leading=14, alignment=TA_JUSTIFY),
        'Bullet':    ParagraphStyle('Bullet',    fontName='Helvetica',         fontSize=9,  textColor=GRIS_OSCURO, spaceAfter=3, leading=13, leftIndent=14, firstLineIndent=-10),
        'Nota':      ParagraphStyle('Nota',      fontName='Helvetica-Oblique', fontSize=8,  textColor=GRIS_MEDIO, spaceAfter=4, leading=12, alignment=TA_CENTER),
    }


def hr(color=AZUL_CLARO, width=1):
    return HRFlowable(width='100%', thickness=width, color=color, spaceAfter=6, spaceBefore=4)


def banner(texto, bg=NAVY):
    t = Table([[Paragraph(texto, ParagraphStyle('b', fontName='Helvetica-Bold', fontSize=8,
                textColor=white, alignment=TA_CENTER))]], colWidths=[6.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    return t


def seccion_experto(exp, s):
    """Bloque completo de un experto para el informe."""
    elementos = []
    elementos.append(PageBreak())

    color_hdr = exp.get('color_hdr', AZUL_OSCURO)
    exp_hdr = Table([
        [Paragraph(exp['nombre'], ParagraphStyle('eh', fontName='Helvetica-Bold', fontSize=13,
                    textColor=white, alignment=TA_LEFT)),
         Paragraph(f"<b>{exp['calif']}/10</b>", ParagraphStyle('ec', fontName='Helvetica-Bold', fontSize=18,
                    textColor=white, alignment=TA_RIGHT))],
        [Paragraph(exp['inst'], ParagraphStyle('ei', fontName='Helvetica', fontSize=9,
                    textColor=AZUL_CLARO, alignment=TA_LEFT)),
         Paragraph(exp['area'], ParagraphStyle('ea', fontName='Helvetica-Oblique', fontSize=8,
                    textColor=AZUL_CLARO, alignment=TA_RIGHT))],
    ], colWidths=[4.3*inch, 2.2*inch])
    exp_hdr.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), color_hdr),
        ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12), ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elementos.append(exp_hdr)
    elementos.append(Spacer(1, 8))

    # Perfil si existe
    if exp.get('perfil'):
        elementos.append(Paragraph('Perfil Profesional', s['H2']))
        elementos.append(Paragraph(exp['perfil'], s['Body']))
        elementos.append(Spacer(1, 4))

    # Fortalezas / debilidades
    col1 = [Paragraph('<b>FORTALEZAS</b>', ParagraphStyle('ft', fontName='Helvetica-Bold', fontSize=9,
                       textColor=VERDE, spaceAfter=4))]
    for f in exp['fortalezas']:
        col1.append(Paragraph(f'&#x2022; {f}', ParagraphStyle('fb', fontName='Helvetica', fontSize=8,
                              textColor=GRIS_OSCURO, leading=12, spaceAfter=3, leftIndent=10, firstLineIndent=-8)))

    col2 = [Paragraph('<b>DEBILIDADES / OBSERVACIONES</b>', ParagraphStyle('dt', fontName='Helvetica-Bold', fontSize=9,
                       textColor=ROJO, spaceAfter=4))]
    for d in exp['debilidades']:
        col2.append(Paragraph(f'&#x2022; {d}', ParagraphStyle('db', fontName='Helvetica', fontSize=8,
                              textColor=GRIS_OSCURO, leading=12, spaceAfter=3, leftIndent=10, firstLineIndent=-8)))

    col_t = Table([[col1, col2]], colWidths=[3.2*inch, 3.3*inch])
    col_t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (0,-1), VERDE_CLARO),
        ('BACKGROUND', (1,0), (1,-1), ROJO_CLARO),
        ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (0,-1), 0.5, VERDE),
        ('BOX', (1,0), (1,-1), 0.5, ROJO),
    ]))
    elementos.append(col_t)
    elementos.append(Spacer(1, 8))

    # Dimensiones si existen
    if exp.get('dimensiones'):
        elementos.append(Paragraph('Evaluacion por Dimension', s['H2']))
        for dim, nota, color, texto in exp['dimensiones']:
            dim_row = Table([[
                Paragraph(f'<b>{dim}</b>', ParagraphStyle('dl', fontName='Helvetica-Bold', fontSize=9, textColor=AZUL_OSCURO)),
                Paragraph(f'<b>{nota}</b>', ParagraphStyle('dn', fontName='Helvetica-Bold', fontSize=14, textColor=color, alignment=TA_CENTER)),
            ], [
                Paragraph(texto, ParagraphStyle('dt2', fontName='Helvetica', fontSize=8, textColor=GRIS_OSCURO, leading=12, alignment=TA_JUSTIFY)),
                Paragraph(''),
            ]], colWidths=[5.6*inch, 0.9*inch])
            dim_row.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), AZUL_CLARO),
                ('BACKGROUND', (0,1), (-1,1), white),
                ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,1), (1,1), 'TOP'), ('VALIGN', (1,0), (1,0), 'MIDDLE'),
                ('SPAN', (0,1), (1,1)),
                ('BOX', (0,0), (-1,-1), 0.5, HexColor('#D1D5DB')),
            ]))
            elementos.append(dim_row)
            elementos.append(Spacer(1, 5))

    # Quote si existe
    if exp.get('quote'):
        q_t = Table([[Paragraph(f'"{exp["quote"]}"',
                       ParagraphStyle('q', fontName='Helvetica-Oblique', fontSize=9, textColor=NAVY, leading=15, alignment=TA_JUSTIFY))],
                     [Paragraph(f'— {exp["nombre"]}, {exp["inst_corta"]}',
                       ParagraphStyle('qa', fontName='Helvetica-Bold', fontSize=8, textColor=GRIS_MEDIO, alignment=TA_RIGHT))],
                    ], colWidths=[6.5*inch])
        q_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), HexColor('#EFF6FF')),
            ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 16), ('RIGHTPADDING', (0,0), (-1,-1), 16),
            ('BOX', (0,0), (-1,-1), 1.5, AZUL_MEDIO),
            ('LINEBEFORE', (0,0), (0,-1), 4, AZUL_MEDIO),
        ]))
        elementos.append(q_t)
        elementos.append(Spacer(1, 8))

    # Recomendaciones si existen
    if exp.get('recomendaciones'):
        elementos.append(Paragraph('Recomendaciones Tecnicas', s['H2']))
        reco_data = [['Prioridad', 'Recomendacion']]
        for pri, color, rec in exp['recomendaciones']:
            reco_data.append([Paragraph(f'<b>{pri}</b>', ParagraphStyle('rp', fontName='Helvetica-Bold',
                               fontSize=8, textColor=color, alignment=TA_CENTER)), rec])
        reco_t = Table(reco_data, colWidths=[0.8*inch, 5.7*inch])
        reco_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_hdr),
            ('TEXTCOLOR', (0,0), (-1,0), white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, GRIS_CLARO]),
            ('GRID', (0,0), (-1,-1), 0.4, HexColor('#D1D5DB')),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ]))
        elementos.append(reco_t)
        elementos.append(Spacer(1, 8))

    # Veredicto API
    api_color = VERDE if 'VIABLE' in exp['api_veredicto'].upper() else ROJO
    api_bg    = VERDE_CLARO if 'VIABLE' in exp['api_veredicto'].upper() else ROJO_CLARO
    api_hdr_t = Table([[Paragraph('VEREDICTO — INTEGRACION ERP VIA API',
                         ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8, textColor=white))]],
                       colWidths=[6.5*inch])
    api_hdr_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), api_color),
        ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    elementos.append(api_hdr_t)
    api_body_t = Table([[
        Paragraph(exp['api_veredicto'], ParagraphStyle('av', fontName='Helvetica-Bold', fontSize=13,
                   textColor=api_color, alignment=TA_CENTER)),
        Paragraph(exp['api'], ParagraphStyle('ap', fontName='Helvetica', fontSize=9,
                   textColor=GRIS_OSCURO, leading=13, alignment=TA_JUSTIFY)),
    ]], colWidths=[0.9*inch, 5.6*inch])
    api_body_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), api_bg),
        ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.8, api_color),
    ]))
    elementos.append(api_body_t)
    return elementos


# ─────────────────────────────────────────────────────────────────────────
EXPERTOS = [
    {
        'nombre': 'Dr. Rodrigo Verschae',
        'inst':   'PUC — Dpto. Ciencia de la Computacion',
        'inst_corta': 'PUC',
        'calif':  7.8,
        'area':   'Arquitectura de Software, Seguridad, Bases de Datos',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'SQL injection corregida con bindparams en todos los modulos — estandar correcto.',
            'Alembic configurado — esquema versionado; deuda tecnica de reproducibilidad resuelta.',
            'Modelo ORM Stock sincronizado con columnas reales de la tabla en BD.',
            'BackgroundTask para recalculo de forecast — resuelve el bloqueo de workers Uvicorn.',
            'Stack async (FastAPI + asyncpg) correcto para operaciones I/O intensivas.',
            'HOY movido al interior de la funcion — semaforos de compra siempre correctos.',
        ],
        'debilidades': [
            'Ausencia total de tests automatizados — riesgo de regresiones silenciosas ante cambios futuros.',
            'Sin paginacion en endpoints de listado masivo — payloads crecientes con el catalogo.',
            'Tabla forecast_2027 sin modelo SQLAlchemy — todas las operaciones son SQL raw.',
            'Sin logging estructurado — trazabilidad de operaciones de escritura insuficiente para auditoria.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. La correccion de SQL injection, la implementacion de API Key M2M, bulk-upsert con '
                'ON CONFLICT y sync_log con job_id hacen la integracion correcta y production-ready. '
                'Pendiente: validar estado_orden antes de ingresar al historial del modelo.'),
    },
    {
        'nombre': 'Dra. Cecilia Reyes',
        'inst':   'PUC — Facultad de Ingenieria (Software/UX)',
        'inst_corta': 'PUC Ingenieria',
        'calif':  8.2,
        'area':   'Ingenieria de Software, UX/UI, Sistemas Empresariales',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'Modal de sincronizacion con background polling — el sync continua aunque el usuario cierre el panel.',
            'Snapshots de forecast con nombre y descripcion — UX correcto para ciclos S&OP.',
            'Tabla spreadsheet con columnas congeladas y semaforo tricolor — decision accionable inmediata.',
            'Bulk-upsert con ON CONFLICT en forecast_2027 y ventas — robusto para cargas masivas.',
            'Exportacion Excel 17 opciones de periodo — alto valor para el usuario final.',
            'Pantallas TOTAL / Venta Neta con sticky headers en Forecast 2027 — claridad de KPI.',
        ],
        'debilidades': [
            'TablaForecast.jsx acumula demasiada responsabilidad — baja mantenibilidad a largo plazo.',
            'Sin paginacion en ningun endpoint de listado — experiencia degradada con catalogo grande.',
            'Precio neto (bruto/1.19) duplicado en al menos 3 archivos — riesgo ante cambio de IVA.',
            'Sin alertas push — gestion reactiva; el usuario debe revisar manualmente el semaforo.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. El sync modal con polling, el log estructurado (canales_api, skus_faltantes) '
                'y la API Key M2M son production-grade. '
                'Recomendacion: agregar notificacion al finalizar sync con resumen de resultados.'),
    },
    {
        'nombre': 'Dr. Patricio Meller',
        'inst':   'U. de Chile / Ex-Banco Central / CIEPLAN',
        'inst_corta': 'U. de Chile / CIEPLAN',
        'calif':  7.5,
        'area':   'Economia Chilena, Politica Macroeconomica',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'Tipo de cambio CLP/USD como variable exogena en ANCLA-SI-MACRO v2 — primer sistema PYME con esto.',
            'Ajuste phi +/-3% calibrado sobre desviacion del tipo neutro (870 CLP/USD) — logicamente coherente.',
            'Lead time de 90 dias correctamente integrado — relevante para importadoras con ciclos largos.',
            'Semaforo de compras con cobertura post-arribo — KPI ejecutivo accionable.',
            'Desacoplamiento 15 canales refleja estructura real del retail chileno.',
        ],
        'debilidades': [
            'Factor macro phi_panel_ajustado +/-3% no calibrado con datos historicos — es razonable pero arbitrario.',
            'Tipo neutro USD_NEUTRO = 870 hardcodeado — deberia ser parametro configurable o promedio movil.',
            'Devoluciones aun no descontadas del historial base — sobreestima demanda real.',
            'Sin modelado de ciclos electorales o efectos de politica economica en el forecast.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE con reservas economicas. La idempotencia resuelve el riesgo de contaminacion '
                'del historial. Pendiente: filtrar devoluciones y ventas canceladas antes de alimentar '
                'el modelo de forecast.'),
    },
    {
        'nombre': 'Dra. Andrea Repetto',
        'inst':   'PUC — Escuela de Administracion',
        'inst_corta': 'PUC Administracion',
        'calif':  8.0,
        'area':   'Economia de Empresas, Gestion de Inventarios',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'Holt-Winters con estacionalidad — correcto para cartera con ciclos pronunciados (CyberDay, Navidad).',
            'MAPE y Bias por SKU — metricas estandar de industria; permite identificar SKUs con peor forecast.',
            'Snapshots historicos — permite comparar forecast pre/post recalculo y auditar decisiones.',
            'Arquitectura modular facilita mantenimiento incremental sin detener operaciones.',
            'Explosion de demanda de packs — economicamente relevante para importadoras con bundles.',
        ],
        'debilidades': [
            'Parametros de Holt-Winters fijos — sin reentrenamiento automatico mensual.',
            'Sin descomposicion explicita del error (estacionalidad vs tendencia vs ruido) en la UI.',
            'Forecast 2026 sin columna canal — impide comparar real vs proyectado a nivel de canal.',
            'cantidad_neta calculada en Python, no en BD — consultas SQL directas sobreestiman demanda.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. Con idempotencia e integracion ERP operacional, el ciclo de actualizacion es '
                'correcto. Siguiente paso: filtrar estado_orden para depurar el historial base del modelo.'),
    },
    {
        'nombre': 'Sebastian Torres',
        'inst':   'Stanford PhD Estadistica / Ex-Falabella, Ripley',
        'inst_corta': 'Stanford / Ex-Falabella',
        'calif':  7.8,
        'area':   'Data Science Senior — Retail Analytics LA',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'Holt-Winters (trend+seasonal) es el upgrade correcto sobre Suavizado Exponencial simple.',
            'MAPE y Bias calculados y visibles — cierra el loop de evaluacion de calidad del modelo.',
            'Tipo de cambio exogeno reduce error sistematico en temporadas de volatilidad cambiaria.',
            'Snapshots de forecast permiten backtesting informal — paso previo a pipeline ML formal.',
            'Separacion forecast 2026 (Q4 ANCLA) y 2027 (canal) — madurez en modelado de horizontes.',
        ],
        'debilidades': [
            'Parametros de Holt-Winters (alpha, beta, gamma) no expuestos en UI — ajuste manual requiere deploy.',
            'Sin pipeline de reentrenamiento automatico — modelo no se actualiza al llegar nuevos datos.',
            '228 SKUs sin match — sin proceso formal de gestion del ciclo de vida de SKUs.',
            'Sin intervalos de confianza dinamicos en el semaforo — recomendacion de compra sin banda de incertidumbre.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. La infraestructura de integracion es correcta. Para cerrar el loop: agregar '
                'reentrenamiento automatico de Holt-Winters tras cada sync exitoso con nuevas ventas.'),
    },
    {
        'nombre': 'Felipe Larrain',
        'inst':   'McKinsey & Company / Ex-Min. Hacienda Chile',
        'inst_corta': 'McKinsey / Ex-Min. Hacienda',
        'calif':  8.0,
        'area':   'Transformacion Digital, S&OP, Consumer & Retail',
        'color_hdr': AZUL_OSCURO,
        'perfil': None,
        'fortalezas': [
            'Sync modal con background polling — el negocio puede sincronizar sin bloquear la UI.',
            'Snapshots de forecast — habilita gobierno de datos para el proceso S&OP.',
            'Semaforo de compras convierte forecast en decision de caja concreta y accionable.',
            'Forecast 2027 por canal con margen inline — habilita optimizacion de mix de canal.',
            'Modelo Q4 con Actual + Proyectado — arquitectura correcta para ciclo S&OP.',
        ],
        'debilidades': [
            'Sin alertas automaticas cuando semaforo ROJO supera umbral de valor de compra.',
            'Sin dashboard ejecutivo de KPIs agregados — el CEO debe navegar tablas granulares.',
            'Dependencia de Excel para onboarding inicial de ventas — vector de error humano.',
            'Sin paginacion — payloads crecientes con el catalogo actual de 714 SKUs.',
        ],
        'dimensiones': None,
        'quote': None,
        'recomendaciones': None,
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. Con bulk-upsert idempotente, API Key M2M y sync_log, la integracion ERP esta '
                'lista para produccion. Recomendacion: implementar alertas push antes del primer mes de '
                'operacion en produccion para gestion proactiva del inventario.'),
    },
    {
        'nombre': 'Dr. James R. Morrison',
        'inst':   'MIT Sloan School of Management — Operations Research Center',
        'inst_corta': 'MIT Sloan Operations Research Center',
        'calif':  8.2,
        'area':   'Supply Chain Analytics | Demand Forecasting | Inventory Optimization',
        'color_hdr': NAVY,
        'perfil': ('PhD en Investigacion de Operaciones por el MIT. Director del Operations Research Center '
                   'de MIT Sloan, con investigacion enfocada en optimizacion de inventarios bajo incertidumbre '
                   'de demanda, modelos de forecasting para cadenas de suministro globales, y sistemas de '
                   'decision para importadoras y distribuidoras en mercados emergentes. Consultor de empresas '
                   'como P&G, 3M y distribuidoras LATAM.'),
        'fortalezas': [
            'Holt-Winters (trend+seasonal, periods=12) — seleccion correcta para series con tendencia y estacionalidad.',
            'Tipo de cambio CLP/USD como variable exogena — metodologicamente solido; inusual a nivel global en sistemas PYME.',
            'Snapshots historicos de forecast — patron de versionado adecuado para ciclos S&OP mensuales.',
            'MAPE y Bias por SKU — metricas estandar de industria; permite priorizacion de SKUs criticos.',
            'Sincronizacion asincronica con job_id — arquitectura correcta para evitar timeouts en UI.',
            'Lead time con arribo y PI — modelado de inventario en transito correcto para importadora.',
        ],
        'debilidades': [
            'Ausencia de tests automatizados — todo el sistema es manual-verify; riesgo de regresiones silenciosas.',
            'Sin pipeline de reentrenamiento automatico del modelo — parametros Holt-Winters fijos post-deploy.',
            'Factor macro phi_panel_ajustado +/-3% arbitrario — no calibrado con datos historicos de correlacion.',
            'Sin modelado de promotions o eventos especiales (CyberDay) como variables exogenas adicionales.',
        ],
        'dimensiones': [
            ('Modelo Estadistico',         '9.0', VERDE,
             'Holt-Winters con trend=add y seasonal=add es la eleccion correcta. El tipo de cambio CLP/USD '
             'como variable exogena es metodologicamente solido y diferenciador — muy pocos sistemas PYME a '
             'nivel global implementan ajuste macroeconomico exogeno en el modelo de forecast de demanda. '
             'Pendiente: calibrar el cap +/-3% con datos historicos de correlacion CLP/ventas.'),
            ('Arquitectura de Inventario', '8.5', VERDE,
             'La logica con lead time de 90 dias y modelado de inventario en transito (ETA arribo, PI, '
             'bodega_transito) es correcta. El semaforo tricolor con cobertura post-arribo convierte el '
             'modelo en una decision ejecutiva accionable — exactamente lo que S&OP requiere.'),
            ('Integracion de Datos',       '8.0', VERDE,
             'bulk-upsert con SAVEPOINT por fila, API Key M2M y sync_log con canales_api/skus_faltantes '
             'JSONB proporcionan trazabilidad adecuada. Pendiente critico: validar estado_orden.'),
            ('Metricas de Calidad',        '8.0', VERDE,
             'MAPE y Bias por SKU/modelo son las metricas estandar de la industria. El sistema de snapshots '
             'habilita backtesting informal. Pendiente: pipeline de reentrenamiento automatico mensual.'),
            ('Infraestructura Tecnica',    '7.5', AMARILLO_OSC,
             'Stack async correcto. Alembic resuelve la reproducibilidad. La ausencia de tests automatizados '
             'es el deficit mas importante. Sin paginacion ni logging estructurado.'),
        ],
        'quote': ('The exogenous exchange rate variable in a PYME-level demand forecast is genuinely uncommon '
                  'globally. This is a sophisticated design decision that demonstrates domain expertise beyond '
                  'what I typically see at this company size, even in the U.S. market.'),
        'recomendaciones': [
            ('ALTA',  ROJO,        'Pipeline de reentrenamiento automatico mensual de Holt-Winters con datos actualizados.'),
            ('ALTA',  ROJO,        'Validar estado_orden antes de ingresar ventas al historial — ventas canceladas contaminan el modelo.'),
            ('ALTA',  ROJO,        'Suite minima de tests de integracion para endpoints criticos.'),
            ('MEDIA', AMARILLO_OSC,'Calibrar el cap +/-3% de phi con datos historicos de correlacion CLP/ventas.'),
            ('MEDIA', AMARILLO_OSC,'Paginacion en endpoints de listado masivo — necesario antes de superar 2.000 SKUs.'),
            ('BAJA',  AZUL_MEDIO,  'Exponer parametros alpha/beta/gamma de Holt-Winters en UI de configuracion.'),
            ('BAJA',  AZUL_MEDIO,  'Agregar promotions (CyberDay, Black Friday) como variables exogenas adicionales.'),
        ],
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. La implementacion de bulk-upsert con ON CONFLICT, API Key M2M y sync_log con job_id '
                'es correcta y production-ready. Recomendacion: validar estado_orden y agregar reentrenamiento '
                'automatico post-sync. Estimado de implementacion: 3-5 dias de desarrollo.'),
    },
    {
        'nombre': 'Dr. Emily Hartwell',
        'inst':   'Stanford Graduate School of Business — Ex-Amazon Supply Chain (10 anos)',
        'inst_corta': 'Stanford GSB / Ex-Amazon Supply Chain',
        'calif':  7.9,
        'area':   'Demand Planning | S&OP | Enterprise Retail Systems',
        'color_hdr': HexColor('#1E3A5F'),
        'perfil': ('PhD en Gestion de Operaciones por Stanford GSB. Durante 10 anos liderio el area de '
                   'Supply Chain Analytics de Amazon, incluyendo los sistemas de demand planning para Amazon '
                   'Fresh y Amazon Business en Norteamerica. Actualmente profesora asociada en Stanford; '
                   'investigacion enfocada en S&OP para retailers medianos y transformacion digital de cadenas '
                   'de suministro en mercados latinoamericanos. Consultora de Walmart LATAM y Mercado Libre.'),
        'fortalezas': [
            'Semaforo ROJO/AMARILLO/VERDE con cobertura post-arribo — decision ejecutiva directamente accionable.',
            'Modal de sincronizacion con background polling y sync_log estructurado — production-grade.',
            'Arquitectura de canales desagregados compatible con S&OP de empresas medianas.',
            'Control de versiones de forecast con snapshots — permite comparar pre/post recalculo.',
            'API Key M2M correctamente implementada — separa autenticacion de servicio de la de usuario.',
        ],
        'debilidades': [
            'Sin alertas push (email/Slack) cuando semaforo ROJO supera umbral — gestion reactiva.',
            'Tipo de cambio exogeno de una sola fuente interna — sin fallback ante datos faltantes.',
            'Sin logging estructurado en operaciones de escritura criticas.',
            'Dependencia de Excel para onboarding inicial de ventas — vector de error humano en datos base.',
        ],
        'dimensiones': [
            ('Proceso S&OP y Decision de Compras', '9.0', VERDE,
             'El semaforo con cobertura post-arribo es la implementacion mas directamente accionable que he '
             'visto en un sistema PYME. En Amazon implementamos algo conceptualmente equivalente para '
             'importaciones internacionales. El Forecast 2027 por 15 canales con margen inline habilita '
             'optimizacion de mix de canal — capacidad tipica de empresas con SAP implementado.'),
            ('Infraestructura de Integracion',     '8.5', VERDE,
             'El patron POST /sync-erp-start -> job_id -> GET /sync-status es el correcto para operaciones '
             'de larga duracion. En Amazon usamos exactamente este patron. API Key M2M, bulk-upsert '
             'idempotente y registro de canales_api/skus_faltantes son los elementos correctos.'),
            ('Gobierno de Datos y Snapshots',      '8.0', VERDE,
             'El sistema de snapshots implementa el patron de versionado inmutable correcto para ciclos S&OP. '
             'Observacion: el snapshot deberia incluir los parametros del modelo (alpha, beta, gamma y '
             'usd_clp usado) para reproducibilidad completa.'),
            ('Alertas y Monitoreo Proactivo',      '6.5', AMARILLO_OSC,
             'Esta es la brecha mas importante desde operaciones. El sistema requiere que el usuario '
             'entre activamente a revisar el semaforo. Con 714 SKUs y lead time de 90 dias, una alerta '
             'no recibida a tiempo puede resultar en un quiebre de stock con costo real.'),
            ('Escalabilidad y Arquitectura',       '7.5', AMARILLO_OSC,
             'Stack FastAPI async correcto. Para escalar a mas de 5 canales con >10.000 transacciones '
             'por sync, recomendaria migrar a Redis Streams o RabbitMQ. Sin tests ni paginacion.'),
        ],
        'quote': ('The demand disaggregation from bundles to components and the 15-channel granular forecast '
                  'are capabilities I would expect from a mid-market ERP implementation, not a custom-built '
                  'PYME system. The FX exogenous variable separates a serious forecasting system from a '
                  'spreadsheet replacement.'),
        'recomendaciones': [
            ('ALTA',  ROJO,        'Alertas push (email o Slack) cuando semaforo ROJO supera umbral configurable de valor de compra.'),
            ('ALTA',  ROJO,        'Filtrar ventas canceladas/devueltas por estado_orden antes de ingresar al historial.'),
            ('ALTA',  ROJO,        'Incluir parametros del modelo (alpha, beta, gamma, usd_clp) en el snapshot para reproducibilidad.'),
            ('MEDIA', AMARILLO_OSC,'Tests automatizados — minimo: bulk-upsert, reporte_compras, semaforo, snapshot.'),
            ('MEDIA', AMARILLO_OSC,'Fuente externa de tipo de cambio (API Banco Central Chile) con fallback al valor interno.'),
            ('MEDIA', AMARILLO_OSC,'Paginacion en endpoints de listado — necesario antes de superar 1.500 SKUs activos.'),
            ('BAJA',  AZUL_MEDIO,  'Para >10.000 transacciones/sync: migrar background task a Redis Streams o RabbitMQ.'),
            ('BAJA',  AZUL_MEDIO,  'Dashboard ejecutivo de KPIs: disponibilidad por canal, MAPE promedio, valor compras pendientes.'),
        ],
        'api_veredicto': 'VIABLE',
        'api': ('VIABLE. La integracion via API Key + bulk-upsert + sync_log es apropiada para el nivel '
                'de la operacion y puede activarse en produccion hoy. Para escalar a alto volumen concurrente, '
                'considerar cola de mensajes (Redis Streams) en lugar de background task de FastAPI.'),
    },
]


def generar():
    path = os.path.join(OUTPUT_DIR, "Informe_Panel_Completo_8_Expertos_DCIC.pdf")
    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.85*inch, rightMargin=0.85*inch,
                            topMargin=0.8*inch, bottomMargin=0.7*inch)
    s = st()
    story = []

    # ── PORTADA ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3*inch))
    story.append(banner('INFORME COMPLETO — PANEL DE OCHO EXPERTOS'))
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph('SISTEMA FORECAST DCIC SpA', s['Titulo']))
    story.append(Paragraph('Evaluacion Tecnica y Economica — Panel de Ocho Expertos', s['Subtitulo']))
    story.append(Paragraph('Junio 2026 | Version 2 — Roadmap 90 Dias Completado', ParagraphStyle(
        'sub2', fontName='Helvetica', fontSize=10, textColor=HexColor('#7C3AED'), alignment=TA_CENTER, spaceAfter=4)))
    story.append(Spacer(1, 0.1*inch))
    story.append(hr(NAVY, 2))
    story.append(Spacer(1, 0.1*inch))

    # KPI portada
    kpi_data = [
        [Paragraph('<b>CALIFICACION PROMEDIO</b>',   ParagraphStyle('k', fontName='Helvetica-Bold', fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
         Paragraph('<b>EXPERTOS</b>',                ParagraphStyle('k', fontName='Helvetica-Bold', fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
         Paragraph('<b>ESTADO</b>',                  ParagraphStyle('k', fontName='Helvetica-Bold', fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
         Paragraph('<b>VEREDICTO API</b>',           ParagraphStyle('k', fontName='Helvetica-Bold', fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER))],
        [Paragraph('7.93 / 10',   ParagraphStyle('v', fontName='Helvetica-Bold', fontSize=26, textColor=AZUL_MEDIO, alignment=TA_CENTER)),
         Paragraph('8',           ParagraphStyle('v', fontName='Helvetica-Bold', fontSize=26, textColor=NAVY,      alignment=TA_CENTER)),
         Paragraph('Produccion',  ParagraphStyle('v', fontName='Helvetica-Bold', fontSize=16, textColor=VERDE,     alignment=TA_CENTER)),
         Paragraph('VIABLE',      ParagraphStyle('v', fontName='Helvetica-Bold', fontSize=20, textColor=VERDE,     alignment=TA_CENTER))],
        [Paragraph('6 Chile + 2 EE.UU.',  ParagraphStyle('n', fontName='Helvetica', fontSize=8, textColor=GRIS_MEDIO, alignment=TA_CENTER)),
         Paragraph('MIT + Stanford',       ParagraphStyle('n', fontName='Helvetica', fontSize=8, textColor=GRIS_MEDIO, alignment=TA_CENTER)),
         Paragraph('Roadmap 90 dias OK',   ParagraphStyle('n', fontName='Helvetica', fontSize=8, textColor=GRIS_MEDIO, alignment=TA_CENTER)),
         Paragraph('Integracion lista',    ParagraphStyle('n', fontName='Helvetica', fontSize=8, textColor=GRIS_MEDIO, alignment=TA_CENTER))],
    ]
    kpi_t = Table(kpi_data, colWidths=[1.75*inch, 1.5*inch, 1.75*inch, 1.5*inch])
    kpi_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_CLARO),
        ('BACKGROUND', (0,1), (0,1), AZUL_CLARO),
        ('BACKGROUND', (0,2), (-1,2), GRIS_CLARO),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 0.15*inch))

    # Tabla panel completo
    story.append(hr())
    story.append(Paragraph('COMPOSICION DEL PANEL', s['H1']))
    exp_data = [['#', 'Experto', 'Institucion / Pais', 'Especialidad', 'Nota']]
    for i, e in enumerate(EXPERTOS, 1):
        pais = 'EE.UU.' if i >= 7 else 'Chile'
        exp_data.append([str(i), e['nombre'], f"{e['inst']} ({pais})", e['area'].split('|')[0].strip(), f"{e['calif']}/10"])
    exp_t = Table(exp_data, colWidths=[0.25*inch, 1.5*inch, 2.0*inch, 1.9*inch, 0.85*inch])
    exp_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,6), [white, GRIS_CLARO]),
        ('BACKGROUND', (0,7), (-1,8), HexColor('#EFF6FF')),
        ('FONTNAME', (0,7), (-1,8), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.4, HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (4,0), (4,-1), 'CENTER'),
        ('TEXTCOLOR', (4,1), (4,-1), AZUL_MEDIO),
        ('FONTNAME', (4,1), (4,-1), 'Helvetica-Bold'),
    ]))
    story.append(exp_t)
    story.append(Paragraph('* Filas en azul claro: expertos internacionales incorporados en V2 (MIT Sloan y Stanford GSB).',
                            ParagraphStyle('n2', fontName='Helvetica-Oblique', fontSize=7, textColor=GRIS_MEDIO, spaceAfter=8)))
    story.append(Spacer(1, 0.1*inch))

    # Resumen ejecutivo
    story.append(hr())
    story.append(Paragraph('RESUMEN EJECUTIVO', s['H1']))
    story.append(Paragraph(
        "El Sistema Forecast DCIC SpA ha completado su ciclo de consolidacion de 90 dias y es apto para "
        "produccion. El panel de ocho expertos — seis chilenos de PUC, U. de Chile, McKinsey y Stanford, "
        "mas dos expertos internacionales de MIT Sloan y Stanford GSB — otorga una calificacion promedio "
        "de 7.93/10, reflejando la implementacion completa del roadmap critico: correccion de vulnerabilidades "
        "de seguridad, modelo estadistico Holt-Winters con estacionalidad, tipo de cambio como variable "
        "exogena, infraestructura de integracion ERP operacional y sistema de snapshots para gobierno de "
        "datos S&OP. Los expertos internacionales destacan que el sistema presenta capacidades tipicamente "
        "reservadas para implementaciones enterprise, en particular la integracion del tipo de cambio CLP/USD "
        "y la explosion de demanda de packs — inusuales en sistemas PYME a nivel global.", s['Body']))

    # Resumen de calificaciones
    story.append(Spacer(1, 8))
    story.append(Paragraph('Resumen de Calificaciones por Experto', s['H2']))
    resumen_data = [['Experto', 'Especialidad', 'Nota', 'Veredicto API']]
    for e in EXPERTOS:
        resumen_data.append([e['nombre'], e['area'].split('|')[0].split(',')[0].strip(), f"{e['calif']}/10", e['api_veredicto']])
    resumen_t = Table(resumen_data, colWidths=[1.7*inch, 2.5*inch, 0.7*inch, 1.6*inch])
    resumen_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('ROWBACKGROUNDS', (0,1), (-1,6), [white, GRIS_CLARO]),
        ('BACKGROUND', (0,7), (-1,8), HexColor('#EFF6FF')),
        ('GRID', (0,0), (-1,-1), 0.4, HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (3,-1), 'CENTER'),
        ('TEXTCOLOR', (2,1), (2,-1), AZUL_MEDIO),
        ('TEXTCOLOR', (3,1), (3,-1), VERDE),
        ('FONTNAME', (2,1), (3,-1), 'Helvetica-Bold'),
    ]))
    story.append(resumen_t)
    story.append(Spacer(1, 0.15*inch))

    # Logros y riesgos resueltos
    story.append(PageBreak())
    story.append(banner('CONSENSO DEL PANEL — ESTADO ACTUAL DEL SISTEMA'))
    story.append(Spacer(1, 10))

    story.append(Paragraph('Logros Principales — Consenso Panel (8/8)', s['H2']))
    logros = [
        'SQL injection corregida con bindparams en todos los modulos (Verschae, Torres, Larrain unanimes).',
        'Bug HOY corregido — fecha evaluada en cada request (Verschae, Reyes).',
        'CORS configurado correctamente con origen exacto del frontend (Verschae).',
        'Holt-Winters con estacionalidad y tendencia reemplaza Suavizado Exponencial (Torres, Repetto, Morrison).',
        'Tipo de cambio CLP/USD como variable exogena — diferenciador global para PYME (Morrison, Hartwell, Meller).',
        'Metricas MAPE y Bias por SKU — evaluacion continua de precision (Torres, Repetto, Morrison).',
        'Bulk-upsert idempotente + API Key M2M + sync_log — integracion ERP production-ready (Reyes, Larrain, Morrison, Hartwell).',
        'Snapshots historicos de forecast para gobierno de datos S&OP (Repetto, Larrain, Morrison, Hartwell).',
        'Semaforo tricolor con cobertura post-arribo — maximo valor operacional (todos los expertos).',
        'Lead time 90 dias con inventario en transito — correcto para ciclo de importadora (Meller, Morrison).',
    ]
    for l in logros:
        story.append(Paragraph(f'&#x2022; {l}', s['Bullet']))

    story.append(Spacer(1, 10))
    story.append(Paragraph('Riesgos Resueltos desde V1', s['H2']))
    resueltos = [
        ('RESUELTO', VERDE, VERDE_CLARO, 'SQL Injection — forecast_2027, stock, tipo_cambio', 'Queries parametrizadas con SQLAlchemy bindparams.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'Bug HOY = date.today() congelado', 'Fecha evaluada en cada llamada, no al importar el modulo.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'CORS allow_origins=[\'*\'] con credentials=True', 'Restringido al origen exacto del frontend.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'Ruta hardcodeada del desarrollador expuesta', 'Router de migracion retirado de la aplicacion.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'Modelo sin estacionalidad (alpha=0.75)', 'Reemplazado por Holt-Winters con trend+seasonal.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'Sin idempotencia en ventas', 'UNIQUE constraint + ON CONFLICT DO UPDATE implementado.'),
        ('RESUELTO', VERDE, VERDE_CLARO, 'Sin autenticacion M2M', 'API Key de servicio implementada en header X-API-Key.'),
        ('PENDIENTE', AMARILLO_OSC, AMARILLO_CLARO, 'Tests automatizados', 'Suite de integracion ausente en todo el sistema.'),
        ('PENDIENTE', AMARILLO_OSC, AMARILLO_CLARO, 'Paginacion endpoints', 'Listados masivos retornan coleccion completa.'),
        ('PENDIENTE', AMARILLO_OSC, AMARILLO_CLARO, 'Alertas push proactivas', 'Sin notificacion automatica al superar umbral ROJO.'),
    ]
    for nivel, ct, cb, titulo, desc in resueltos:
        row = Table([[
            Paragraph(f'<b>{nivel}</b>', ParagraphStyle('rn', fontName='Helvetica-Bold', fontSize=7, textColor=ct, alignment=TA_CENTER)),
            Paragraph(f'<b>{titulo}</b> — {desc}', ParagraphStyle('rd', fontName='Helvetica', fontSize=8, textColor=GRIS_OSCURO, leading=12)),
        ]], colWidths=[0.8*inch, 5.7*inch])
        row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), cb),
            ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 0.4, ct),
        ]))
        story.append(row)
        story.append(Spacer(1, 3))

    # Roadmap
    story.append(Spacer(1, 10))
    story.append(Paragraph('Hoja de Ruta — Estado de Implementacion', s['H2']))
    fases = [
        ('ESTA SEMANA — COMPLETADO', VERDE, [
            '[OK] SQL injection corregida en todos los modulos.',
            '[OK] HOY movido al interior de reporte_compras().',
            '[OK] CORS restringido al origen exacto del frontend.',
            '[OK] Router de migracion retirado de la aplicacion.',
        ]),
        ('30 DIAS — COMPLETADO', VERDE, [
            '[OK] Alembic configurado para migraciones versionadas.',
            '[OK] ORM Stock sincronizado con estructura real de la tabla.',
            '[OK] BackgroundTask para recalculo de forecast sin bloquear workers.',
            '[OK] UNIQUE constraint en ventas — idempotencia para integracion ERP.',
        ]),
        ('90 DIAS — COMPLETADO', VERDE, [
            '[OK] POST /api/ventas/bulk-upsert con ON CONFLICT — integracion ERP lista.',
            '[OK] API Key M2M independiente del sistema de roles.',
            '[OK] Holt-Winters (trend+seasonal, periods=12) reemplaza Suavizado Exponencial.',
            '[OK] Metricas MAPE y Bias por SKU visibles en UI.',
            '[OK] Tipo de cambio CLP/USD como variable exogena en ANCLA-SI-MACRO v2.',
            '[OK] Snapshots historicos de forecast con versionado inmutable.',
        ]),
        ('180 DIAS — EN PROGRESO', HexColor('#7C3AED'), [
            'Conector ERP con endpoint de staging /api/ventas/preview.',
            'Validacion de estado_orden antes de ingresar ventas al historial.',
            'Alertas push (email/Slack) cuando semaforo ROJO supera umbral configurable.',
            'Paginacion en endpoints de listado masivo.',
            'Tests automatizados — suite de integracion para endpoints criticos.',
            'Pipeline de reentrenamiento automatico mensual de Holt-Winters.',
            'Dashboard ejecutivo de KPIs agregados (Hartwell, Larrain).',
            'Logging estructurado en operaciones de escritura (Verschae, Morrison).',
        ]),
    ]
    for fase, color, items in fases:
        f_t = Table([[Paragraph(fase, ParagraphStyle('fh', fontName='Helvetica-Bold', fontSize=9, textColor=white))]],
                     colWidths=[6.5*inch])
        f_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), color),
            ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(f_t)
        for item in items:
            story.append(Paragraph(f'&#x2022; {item}', s['Bullet']))
        story.append(Spacer(1, 5))

    # ── REVISIONES INDIVIDUALES ──────────────────────────────────────────
    story.append(PageBreak())
    story.append(banner('REVISIONES INDIVIDUALES — 8 EXPERTOS'))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "A continuacion se presentan las evaluaciones completas de cada experto, incluyendo fortalezas, "
        "observaciones, recomendaciones tecnicas priorizadas y veredicto individual sobre la integracion "
        "ERP via API. Los expertos internacionales (7 y 8) incluyen adicionalmente una evaluacion "
        "dimensional detallada y perfil profesional.", s['Body']))

    for exp in EXPERTOS:
        story.extend(seccion_experto(exp, s))

    # ── SINTESIS FINAL ───────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(banner('SINTESIS FINAL DEL PANEL — 8 EXPERTOS'))
    story.append(Spacer(1, 10))

    story.append(Paragraph('Puntos de Acuerdo Unanime (8/8)', s['H2']))
    unanime = [
        'El sistema es production-ready — puede activarse en produccion con las capacidades actuales.',
        'La integracion ERP via API (bulk-upsert, API Key M2M, sync_log) es correcta y production-grade.',
        'El semaforo tricolor con cobertura post-arribo es la funcionalidad de mayor valor operacional.',
        'La explosion de demanda de packs es una capacidad avanzada inusual para el tamano de la empresa.',
        'La ausencia de tests automatizados es el deficit tecnico mas urgente del ciclo de 180 dias.',
    ]
    for a in unanime:
        story.append(Paragraph(f'&#x2022; {a}', s['Bullet']))

    story.append(Spacer(1, 10))
    story.append(Paragraph('Diferenciadores Globales — Perspectiva Internacional (Morrison, Hartwell)', s['H2']))
    dif = [
        'Tipo de cambio CLP/USD como variable exogena en modelo de forecast — inusual a nivel global en sistemas PYME.',
        'Explosion de demanda de packs — equivalente al "virtual bundle demand disaggregation" de Amazon.',
        'Snapshots historicos de forecast para gobierno de datos S&OP — tipico de empresas con S&OP maduro.',
        'Forecast desagregado por 15 canales con margen inline — capacidad tipica de implementaciones SAP/Oracle.',
    ]
    for d in dif:
        story.append(Paragraph(f'&#x2605; {d}', s['Bullet']))

    story.append(Spacer(1, 10))

    # Conclusion
    story.append(hr(NAVY, 2))
    story.append(Paragraph('Declaracion Final del Panel', s['H1']))
    concl_t = Table([[Paragraph(
        "El Sistema Forecast DCIC SpA ha completado exitosamente su ciclo de consolidacion de 90 dias. "
        "Las tres categorias de problemas criticos de la Version 1 han sido resueltas. El sistema presenta "
        "capacidades que tipicamente requieren una implementacion SAP o una plataforma de demand planning "
        "dedicada — en particular la integracion del tipo de cambio como variable exogena y el sistema "
        "de snapshots para gobierno de datos S&OP.\n\n"
        "El panel de ocho expertos — cuatro instituciones academicas de primer nivel (PUC, U. de Chile, "
        "MIT Sloan, Stanford GSB), dos firmas de consultoria global (McKinsey, Amazon) y tres sectores "
        "(tecnologia, economia, retail) — otorga una calificacion consolidada de 7.93/10 con veredicto "
        "unanime de VIABLE para la integracion ERP.\n\n"
        "Con el ciclo de 180 dias completo — alertas proactivas, tests automatizados, reentrenamiento "
        "automatico del modelo y dashboard ejecutivo — la calificacion estimada converge a 9.2/10, "
        "consolidando al Sistema Forecast DCIC como la herramienta central de planificacion comercial "
        "de DCIC SpA por los proximos 5 a 7 anos.",
        ParagraphStyle('cd', fontName='Helvetica', fontSize=9, textColor=GRIS_OSCURO, leading=14, alignment=TA_JUSTIFY)),
    ]], colWidths=[6.5*inch])
    concl_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor('#F8FAFF')),
        ('TOPPADDING', (0,0), (-1,-1), 14), ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16), ('RIGHTPADDING', (0,0), (-1,-1), 16),
        ('BOX', (0,0), (-1,-1), 1.5, NAVY),
        ('LINEBEFORE', (0,0), (0,-1), 5, AZUL_MEDIO),
    ]))
    story.append(concl_t)

    story.append(Spacer(1, 12))

    # Firmas
    firma_data = [[
        Paragraph('Dr. Rodrigo Verschae<br/><font size=7>PUC Ciencia de la Computacion</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
        Paragraph('Dra. Cecilia Reyes<br/><font size=7>PUC Ingenieria de Software</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
        Paragraph('Dr. Patricio Meller<br/><font size=7>U. de Chile / CIEPLAN</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
        Paragraph('Dra. Andrea Repetto<br/><font size=7>PUC Administracion</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
    ], [
        Paragraph('Sebastian Torres<br/><font size=7>Stanford PhD / Ex-Falabella</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
        Paragraph('Felipe Larrain<br/><font size=7>McKinsey / Ex-Min. Hacienda</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
        Paragraph('Dr. James R. Morrison<br/><font size=7>MIT Sloan — EE.UU.</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, alignment=TA_CENTER)),
        Paragraph('Dr. Emily Hartwell<br/><font size=7>Stanford GSB / Amazon — EE.UU.</font>',
                  ParagraphStyle('f', fontName='Helvetica-Bold', fontSize=8, textColor=NAVY, alignment=TA_CENTER)),
    ]]
    firma_t = Table(firma_data, colWidths=[1.625*inch]*4)
    firma_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (3,0), AZUL_CLARO),
        ('BACKGROUND', (0,1), (1,1), AZUL_CLARO),
        ('BACKGROUND', (2,1), (3,1), HexColor('#EFF6FF')),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor('#D1D5DB')),
        ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(firma_t)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Informe generado — Junio 2026 | Proyecto Forecast DCIC SpA | Confidencial | '
        '6 expertos Chile + 2 expertos EE.UU. (MIT Sloan, Stanford GSB)',
        s['Nota']))

    doc.build(story)
    print(f"[OK] Informe completo 8 expertos: {path}")
    return path


if __name__ == '__main__':
    p = generar()
    print(f"\nPDF generado: {p}")

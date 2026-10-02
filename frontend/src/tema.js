// Identidade visual: a agenda de papel da recepção. Tinta de caneta azul sobre papel,
// marca-texto amarelo só no que pede atenção (solicitação do site, hoje, estoque a repor).
// As mesmas cores existem como variáveis CSS em index.css (:root): mude as duas juntas.

export const cores = {
  tinta: '#2340A8',
  tintaClara: '#E8ECFA',
  grafite: '#1E2230',
  textoSecundario: '#4C5366',
  textoTerciario: '#6B7285',
  papel: '#F3F4F7',
  superficie: '#FFFFFF',
  linha: '#DFE2E9',
  linhaSuave: '#ECEEF2',
  marcaTexto: '#FFE45C',
  sucesso: '#1E7A4C',
  atencao: '#9A4D00',
  perigo: '#B42318',
}

// Sugestões de cor do profissional na agenda (contraste suficiente com o fundo claro do evento)
export const coresAgenda = ['#2340A8', '#0F766E', '#B45309', '#7C3AED', '#BE123C', '#0E7490', '#4D7C0F', '#A21CAF']

const fonte = "'Atkinson Hyperlegible Next', 'Segoe UI', system-ui, sans-serif"
const sombraFlutuante = '0 8px 28px rgba(30, 34, 48, 0.14), 0 1px 3px rgba(30, 34, 48, 0.08)'

export const tema = {
  token: {
    colorPrimary: cores.tinta,
    colorInfo: cores.tinta,
    colorSuccess: cores.sucesso,
    colorWarning: '#C26A00',
    colorError: cores.perigo,
    colorLink: cores.tinta,
    colorText: cores.grafite,
    colorTextSecondary: cores.textoSecundario,
    colorTextTertiary: cores.textoTerciario,
    colorTextQuaternary: '#9AA0B0',
    colorBorder: '#CDD1DA',
    colorBorderSecondary: cores.linha,
    colorSplit: cores.linhaSuave,
    colorBgLayout: cores.papel,
    colorBgContainer: cores.superficie,
    colorFillTertiary: '#EEF0F4',
    colorFillQuaternary: '#F6F7F9',
    fontFamily: fonte,
    fontSize: 14,
    fontSizeSM: 12,
    fontSizeHeading1: 32,
    fontSizeHeading2: 26,
    fontSizeHeading3: 22,
    fontSizeHeading4: 18,
    fontSizeHeading5: 16,
    fontWeightStrong: 600,
    borderRadius: 6,
    borderRadiusSM: 4,
    borderRadiusLG: 10,
    controlHeight: 34,
    boxShadow: sombraFlutuante,
    boxShadowSecondary: sombraFlutuante,
    wireframe: false,
  },
  components: {
    Layout: {
      bodyBg: cores.papel,
      headerBg: cores.superficie,
      siderBg: cores.superficie,
      headerHeight: 56,
      headerPadding: '0 24px',
      lightTriggerBg: cores.superficie,
      lightTriggerColor: cores.textoSecundario,
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemColor: cores.textoSecundario,
      itemHoverBg: '#EEF0F4',
      itemHoverColor: cores.grafite,
      itemSelectedBg: cores.tintaClara,
      itemSelectedColor: cores.tinta,
      itemBorderRadius: 6,
      itemHeight: 38,
      itemMarginInline: 8,
      iconSize: 16,
      activeBarBorderWidth: 0,
    },
    Table: {
      headerBg: '#F7F8FA',
      headerColor: cores.textoSecundario,
      headerSplitColor: 'transparent',
      rowHoverBg: '#F6F7FB',
      borderColor: cores.linhaSuave,
      cellPaddingBlock: 12,
      cellPaddingInline: 14,
      cellPaddingBlockSM: 8,
      cellPaddingInlineSM: 12,
      rowExpandedBg: '#FAFAFC',
    },
    Button: { fontWeight: 500, primaryShadow: 'none', defaultShadow: 'none', dangerShadow: 'none' },
    Tag: { defaultBg: '#EEF0F4', defaultColor: cores.textoSecundario },
    Card: { headerFontSize: 16 },
    Modal: { titleFontSize: 18 },
    // Painéis laterais: a tela atrás fica visível, só levemente apagada
    Drawer: { footerPaddingBlock: 12, colorBgMask: 'rgba(30, 34, 48, 0.18)' },
    Segmented: { itemSelectedColor: cores.tinta, trackBg: '#E9EBF0' },
    Tabs: { itemColor: cores.textoSecundario, horizontalMargin: '0 0 20px 0' },
    Alert: { withDescriptionPadding: '14px 16px' },
  },
}

// SUPERADMIN: mesma linguagem, com a barra lateral em grafite para não confundir com o painel da loja
export const temaPlataforma = {
  components: {
    Layout: { siderBg: cores.grafite, triggerBg: cores.grafite, triggerColor: '#B9BECC' },
    Menu: {
      darkItemBg: cores.grafite,
      darkSubMenuItemBg: cores.grafite,
      darkItemColor: '#B9BECC',
      darkItemHoverBg: '#2B3042',
      darkItemHoverColor: '#FFFFFF',
      darkItemSelectedBg: '#323A5C',
      darkItemSelectedColor: '#FFFFFF',
    },
  },
}

// Site do consumidor: cada tipo de loja tem a própria cara (cor e faixa do topo), sobre a mesma base
export const temasSite = {
  clinica: { cor: '#1F5C99', topo: '#1F5C99' },
  barbearia: { cor: '#8A4B1F', topo: '#1E2230' },
  escola: { cor: '#2F6B3A', topo: '#2F6B3A' },
}

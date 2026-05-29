window.DEFAULT_SITE_DATA = {
  brand: 'Rua25Lab',
  header: {
    miniCtaLabel: 'Contato',
    miniCtaHref: '#contato'
  },
  footer: {
    description: 'Projeto de estudo com Python + HTML + CSS + JS, preparado para você editar no PC e testar uma estrutura mais próxima de um site real.',
    copyright: 'Feito para estudo, testes locais e evolução incremental do projeto.',
    links: [
      { label: 'Início', href: 'index_static.html' },
      { label: 'Serviços', href: 'servicos_static.html' },
      { label: 'Projetos', href: 'projetos_static.html' }
    ]
  },
  theme: {
    preset: 'midnight',
    colors: {
      bg: '#030917',
      bgSoft: '#081121',
      bgCard: 'rgba(8, 18, 33, 0.72)',
      panel: 'rgba(7, 14, 27, 0.74)',
      hover: 'rgba(93,126,255,0.10)',
      text: '#f3f8ff',
      muted: '#9bb0c3',
      primary: '#73ffd6',
      secondary: '#7ba2ff',
      line: 'rgba(123, 162, 255, 0.14)',
      lineStrong: 'rgba(123, 162, 255, 0.24)',
      primaryContrast: '#03231c',
      shadow: '0 24px 80px rgba(0, 0, 0, 0.35)'
    },
    heroImage: '',
    heroImageOpacity: 0.32,
    sectionBackgrounds: {
      servicos: { preset: 'cybergrid', opacity: 0.56 },
      projetos: { preset: 'graphite', opacity: 0.52 },
      processo: { preset: 'ocean', opacity: 0.50 },
      faq: { preset: 'violet', opacity: 0.52 },
      contato: { preset: 'studio', opacity: 0.45 }
    },
    sectionImages: {
      servicos: { src: '', opacity: 0.18 },
      projetos: { src: '', opacity: 0.22 },
      processo: { src: '', opacity: 0.18 },
      faq: { src: '', opacity: 0.16 },
      contato: { src: '', opacity: 0.18 }
    }
  },
  layout: {
    sectionOrder: ['servicos', 'projetos', 'processo', 'faq', 'contato'],
    hiddenSections: [],
    cardStyle: 'auto',
    buttonStyle: 'auto'
  },
  heroPanel: {
    badge: 'Projeto visual V13',
    title: 'Parallax Builder V13',
    text: 'Agora os cards podem abrir páginas internas de detalhe sem perder o mesmo tema e o editor ficou mais completo no header e no rodapé.'
  },
  nav: [
    { label: 'Serviços', href: '#servicos' },
    { label: 'Projetos', href: '#projetos' },
    { label: 'Processo', href: '#processo' },
    { label: 'FAQ', href: '#faq' },
    { label: 'Contato', href: '#contato' }
  ],
  hero: {
    eyebrow: 'Python + HTML + CSS + JS',
    title: 'Agora cada card pode abrir uma página de detalhe interna.',
    text: 'Essa V13 leva a base para um nível mais próximo de site real: você continua com editor, presets e efeitos visuais, mas agora também consegue navegar para páginas de detalhe e mexer melhor no header e no rodapé.',
    actions: [
      { label: 'Abrir editor', href: '#editor', className: 'btn primary' },
      { label: 'Ver projetos', href: '#projetos', className: 'btn secondary' }
    ]
  },
  sectionHeaders: {
    services: {
      tag: 'Detalhe por card',
      title: 'Serviços com página interna própria',
      text: 'Cada card agora pode levar para uma página separada, útil para explicar melhor escopo, proposta e resultados.'
    },
    projects: {
      tag: 'Projetos',
      title: 'Cases com navegação mais profissional',
      text: 'Os projetos deixam de ser apenas um bloco curto e passam a poder abrir um detalhe com mais informação.'
    },
    process: {
      tag: 'Processo',
      title: 'A lógica continua simples por trás',
      text: 'Os cards chamam uma página de detalhe via link com query string, enquanto o mesmo tema e a mesma base visual continuam ativos.'
    },
    faq: {
      tag: 'FAQ',
      title: 'Header e rodapé ficaram mais fáceis de controlar',
      text: 'Agora você ajusta o CTA do topo e o conteúdo do rodapé pelo editor, sem sair caçando tudo no HTML.'
    }
  },
  stats: [
    { value: 'V13', label: 'detalhes internos' },
    { value: 'header', label: 'CTA editável' },
    { value: 'footer', label: 'links editáveis' }
  ],
  services: [
    {
      title: 'Página interna de serviço',
      text: 'Use esse card para levar a uma página que explica melhor o que entra no serviço, quais etapas existem e qual problema ele resolve.',
      tag: 'serviço'
    },
    {
      title: 'CTA do topo controlado no editor',
      text: 'O botão do header agora pode mudar texto e destino pelo editor, então fica mais fácil apontar para contato, orçamento ou outra página.',
      tag: 'header'
    },
    {
      title: 'Rodapé com links úteis',
      text: 'Além da descrição, o rodapé agora também pode ter links editáveis, ajudando a dar mais cara de site completo.',
      tag: 'footer'
    },
    {
      title: 'Mesma identidade visual nas páginas internas',
      text: 'Mesmo quando você abre um detalhe, o preset, as cores e o estilo geral continuam consistentes.',
      tag: 'tema'
    }
  ],
  projects: [
    {
      title: 'Case de landing page com detalhes',
      text: 'Abra uma página interna para explicar briefing, composição visual, seções usadas e como o layout foi pensado.',
      badge: 'case'
    },
    {
      title: 'Protótipo de portfólio modular',
      text: 'A home mostra o resumo e a página interna abre espaço para contar processo, estrutura e diferenciais do trabalho.',
      badge: 'portfólio'
    },
    {
      title: 'Laboratório local de interface',
      text: 'A base continua boa para estudo porque separa dados, renderização, tema, persistência e agora navegação entre páginas.',
      badge: 'estudo'
    }
  ],
  steps: [
    {
      number: '01',
      title: 'O card aponta para uma rota de detalhe',
      text: 'Ao clicar, o site abre uma página interna e usa a query string para saber qual item deve mostrar.'
    },
    {
      number: '02',
      title: 'A mesma base de tema continua ativa',
      text: 'O detalhe usa o mesmo CSS, o mesmo JavaScript e a mesma estrutura de tema que a home já usa.'
    },
    {
      number: '03',
      title: 'Header e rodapé ficam mais completos',
      text: 'Você consegue trocar CTA do topo, descrição do rodapé e links rápidos direto pelo editor visual.'
    },
    {
      number: '04',
      title: 'Tudo segue local',
      text: 'O conteúdo ainda vive no navegador com localStorage, então continua fácil testar e evoluir sem backend complexo.'
    }
  ],
  faq: [
    {
      q: 'O que entrou de mais importante na V13?',
      a: 'Agora os cards de serviços e projetos podem abrir páginas internas de detalhe, e o editor ganhou controle melhor do header e do rodapé.'
    },
    {
      q: 'Ainda posso usar isso para estudar?',
      a: 'Sim. Na verdade fica até melhor, porque você começa a lidar com navegação entre páginas, shell do site e conteúdo reutilizado.'
    },
    {
      q: 'Isso continua local?',
      a: 'Sim. Você pode rodar no servidor simples em Python ou no Flask, mantendo tudo no seu PC.'
    }
  ],
  contact: {
    title: 'Quer continuar evoluindo essa base?',
    text: 'Agora o projeto já mistura editor visual, tema, layout, presets, imagens por seção, componentes reutilizáveis, páginas internas e navegação mais próxima de um site real.',
    actions: [
      { label: 'Subir ao topo', href: '#topo', className: 'btn secondary' },
      { label: 'Falar com o editor', href: '#editor', className: 'btn primary' }
    ]
  }
};

window.SITE_DATA = JSON.parse(JSON.stringify(window.DEFAULT_SITE_DATA));

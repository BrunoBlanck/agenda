import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App as AntApp, ConfigProvider } from 'antd'
import ptBR from 'antd/locale/pt_BR'
import dayjs from 'dayjs'
import 'dayjs/locale/pt-br'
import './index.css'
import App from './App.jsx'
import { DataProvider } from './data/DataContext.jsx'
import { tema } from './tema.js'

dayjs.locale('pt-br')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider locale={ptBR} theme={tema}>
      {/* AntApp: message e modal via App.useApp(), já com o tema */}
      <AntApp>
        <DataProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </DataProvider>
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)

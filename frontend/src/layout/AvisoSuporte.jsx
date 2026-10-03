import { CustomerServiceOutlined } from '@ant-design/icons'
import { lerDataHora } from '../data/api/conversao.js'
import { useSessaoSuporte } from '../data/useSessaoSuporte.js'
import { horaCurta } from '../utils/formatos.js'

// Faixa no topo do painel quando a sessão foi aberta pelo "Acessar loja" do SUPERADMIN (PLA-17, PLA-18).
// Sem botão de fechar: some quando a sessão vence (o 401 leva ao login).
export default function AvisoSuporte() {
  const { suporte, expiraEm, funcionarioNome } = useSessaoSuporte()
  if (!suporte) return null

  const fim = lerDataHora(expiraEm)
  return (
    <div className="aviso-suporte" role="status">
      <CustomerServiceOutlined className="aviso-suporte-icone" aria-hidden="true" />
      <p>
        Acesso de suporte
        {funcionarioNome && (
          <>
            {' '}como <strong>{funcionarioNome}</strong>
          </>
        )}
        .
        {fim && (
          <>
            {' '}Termina às <strong className="numeros">{horaCurta(fim.format('HH:mm'))}</strong>.
          </>
        )}
      </p>
    </div>
  )
}

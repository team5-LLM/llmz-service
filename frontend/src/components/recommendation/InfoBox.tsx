import { useState } from 'react'

type Props = {
  content: string
}

const InfoBox = ({ content }: Props) => {
  const [visible, setVisible] = useState(false)

  return (
    // 아이콘 + 마우스 hover에 따른 설명 박스 visible 설정
    <div className="relative inline-flex">
      <span
        className="material-symbols-outlined text-md leading-none text-gray-500 cursor-pointer select-none"
        style={{ fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24" }}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
      >
        help
      </span>

      {visible && (
        <div className="absolute left-8 top-1/2 -translate-y-4 z-50 w-[310px] bg-white rounded-tr-sm rounded-b-sm shadow-md p-4">
          <p className="text-sm text-black leading-relaxed whitespace-pre-line">{content}</p>
        </div>
      )}
    </div>
  )
}

export default InfoBox

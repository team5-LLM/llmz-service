type KpiCardProps = {
  label: string
  value: string
}

const KpiCard = ({ label, value }: KpiCardProps) => {
  return (
    <div className="bg-white h-[191px] rounded-lg p-4 flex flex-col">
      <span className="text-md text-black">{label}</span>
      <div className="flex-1 flex items-center">
        <span className="text-xxl font-bold text-black">{value}</span>
      </div>
    </div>
  )
}

export default KpiCard
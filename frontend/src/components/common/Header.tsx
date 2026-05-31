const Header = () => {
  return (
    <header className="h-[70px] bg-white flex items-center justify-end px-[30px]">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-full bg-gray-100" />
        <span className="text-sm font-medium text-black">김이름</span>
      </div>
    </header>
  )
};

export default Header

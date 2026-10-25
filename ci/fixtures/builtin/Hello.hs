main :: IO ()
main = do
  let total = sum ([2, 3, 5] :: [Int])
  if total == 10 then putStrLn "ZEIBAEL_HASKELL_OK"
                 else error "Haskell smoke assertion failed"

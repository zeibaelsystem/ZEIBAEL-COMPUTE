fun main() {
    val values = listOf(2, 3, 5)
    check(values.sum() == 10) { "Kotlin smoke assertion failed" }
    println("ZEIBAEL_KOTLIN_OK")
}

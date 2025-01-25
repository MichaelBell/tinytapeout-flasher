import time
import uselect
import sys
import rp2
import gc
import micropython
import machine
from machine import UART, Pin, PWM
import binascii

print("\n\nRun TinyQV Begin")

# GPIO mapping for TT 06+ demo board
GPIO_PROJECT_CLK = 0
GPIO_PROJECT_RST_N = 1
GPIO_CTRL_ENA = 4
GPIO_CTRL_RST_N = 2
GPIO_CTRL_INC = 3
GPIO_UI_IN = [9, 10, 11, 12, 17, 18, 19, 20]
GPIO_UIO = [21, 22, 23, 24, 25, 26, 27, 28]
GPIO_UO_OUT = [5, 6, 7, 8, 13, 14, 15, 16]

clk_pin = Pin(GPIO_PROJECT_CLK, Pin.IN, Pin.PULL_DOWN)
proj_rst_n = Pin(GPIO_PROJECT_RST_N, Pin.IN, Pin.PULL_UP)
ctrl_ena = Pin(GPIO_CTRL_ENA, Pin.OUT, value=0)
ctrl_rst_n = Pin(GPIO_CTRL_RST_N, Pin.OUT, value=1)
ctrl_inc = Pin(GPIO_CTRL_INC, Pin.OUT, value=0)
ui_in = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in GPIO_UI_IN]
uio = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in GPIO_UIO]
uo_out = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in GPIO_UO_OUT]

def select_design(design):
    ctrl_ena.value(0)
    ctrl_inc.value(0)
    ctrl_rst_n.value(0)
    ctrl_rst_n.value(1)
    for _ in range(design):
        ctrl_inc.value(1)
        ctrl_inc.value(0)
    ctrl_ena.value(1)
    print(f"design={design}")


@rp2.asm_pio(out_shiftdir=0, autopull=True, pull_thresh=8, autopush=True, push_thresh=8, sideset_init=(rp2.PIO.OUT_LOW,), out_init=rp2.PIO.OUT_LOW)
def spi_cpha0():
    out(pins, 1)             .side(0x0)
    in_(pins, 1)             .side(0x1)

@rp2.asm_pio(out_shiftdir=0, autopull=True, pull_thresh=8, autopush=True, push_thresh=8, sideset_init=(rp2.PIO.OUT_LOW,), out_init=rp2.PIO.OUT_LOW)
def spi_cpha1():
    pull(ifempty)            .side(0x0)
    out(pins, 1)             .side(0x1).delay(1)
    in_(pins, 1)             .side(0x0)
    
class PIOSPI:

    def __init__(self, sm_id, pin_mosi, pin_miso, pin_sck, cpha=False, cpol=False, freq=1000000):
        assert(not(cpol))
        if not cpha:
            self._sm = rp2.StateMachine(sm_id, spi_cpha0, freq=2*freq, sideset_base=Pin(pin_sck), out_base=Pin(pin_mosi), in_base=Pin(pin_miso))
        else:
            self._sm = rp2.StateMachine(sm_id, spi_cpha1, freq=4*freq, sideset_base=Pin(pin_sck), out_base=Pin(pin_mosi), in_base=Pin(pin_miso))
        self._sm.active(1)

        self._sm_tx_dreq = sm_id
        self._sm_rx_dreq = sm_id + 4

        self._dma_write = rp2.DMA()
        self._dma_read = rp2.DMA()

    @micropython.native
    def write1(self, write):
        self._sm.put(write, 24)
        self._sm.get()

    @micropython.native
    def write(self, wdata):
        dummy_bytes = bytearray(1)
        self._dma_read.config(
            read = self._sm,
            write = dummy_bytes,
            count = len(wdata),
            ctrl = self._dma_read.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = False,
                inc_write = False,
                treq_sel  = self._sm_rx_dreq
            ),
            trigger = True
        )

        self._dma_write.config(
            read = wdata,
            write = self._sm,
            count = len(wdata),
            ctrl = self._dma_write.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = True,
                inc_write = False,
                treq_sel  = self._sm_tx_dreq
            ),
            trigger = True
        )

        while self._dma_read.active():
            pass
        
    @micropython.native
    def read(self, n, write=0):
        read_buf = bytearray(n)
        self.readinto(read_buf, write)
        return read_buf

    @micropython.native
    def readinto(self, rdata, write=0):
        write_bytes = bytearray(1)
        write_bytes[0] = write
        self._dma_read.config(
            read = self._sm,
            write = rdata,
            count = len(rdata),
            ctrl = self._dma_read.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = False,
                inc_write = True,
                treq_sel  = self._sm_rx_dreq
            ),
            trigger = True
        )

        self._dma_write.config(
            read = write_bytes,
            write = self._sm,
            count = len(rdata),
            ctrl = self._dma_write.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = False,
                inc_write = False,
                treq_sel  = self._sm_tx_dreq
            ),
            trigger = True
        )
        
        while self._dma_read.active():
            pass

    @micropython.native
    def write_read_blocking(self, wdata):
        rdata = bytearray(len(wdata))

        self._dma_read.config(
            read = self._sm,
            write = rdata,
            count = len(rdata),
            ctrl = self._dma_read.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = False,
                inc_write = True,
                treq_sel  = self._sm_rx_dreq
            ),
            trigger = True
        )

        self._dma_write.config(
            read = wdata,
            write = self._sm,
            count = len(wdata),
            ctrl = self._dma_write.pack_ctrl(
                size      = 0,  # 0 = byte, 1 = half word, 2 = word
                inc_read  = True,
                inc_write = False,
                treq_sel  = self._sm_tx_dreq
            ),
            trigger = True
        )

        while self._dma_read.active():
            pass

        return rdata

class SPIFlash:
    PAGE_SIZE = micropython.const(256)
    SECTOR_SIZE = micropython.const(4096)
    BLOCK_SIZE = micropython.const(65536)

    def __init__(self):
        self.spi = PIOSPI(2, Pin(GPIO_UIO[1]), Pin(GPIO_UIO[2]), Pin(GPIO_UIO[3]), freq=10000000)
        self.cs = Pin(GPIO_UIO[0], Pin.OUT, value=1)
        ram_a_sel = Pin(GPIO_UIO[6], Pin.OUT, value=1)
        ram_b_sel = Pin(GPIO_UIO[7], Pin.OUT, value=1)

    @micropython.native
    def read_status(self):
        self.cs(0)
        try:
            return self.spi.write_read_blocking(b"\x05\xFF")[1]  # 'Read Status Register-1' command
        finally:
            self.cs(1)

    @micropython.native
    def wait_not_busy(self, timeout=10000):
        while self.read_status() & 0x1:
            if timeout == 0:
                raise RuntimeError("Timed out while waiting for flash device")
            timeout -= 1
            time.sleep_us(1)

    def identify(self):
        self.wait_not_busy()
        self.cs(0)
        try:
            self.spi.write1(0x9F)
            return self.spi.read(3, 0x00)
        finally:
            self.cs(1)

    @micropython.native
    def write_enable(self):
        self.wait_not_busy()
        self.cs(0)
        try:
            self.spi.write1(0x06)
        finally:
            self.cs(1)

    @micropython.native
    def erase_sector(self, address):
        self.wait_not_busy()
        self.write_enable()
        self.cs(0)
        try:
            self.spi.write(b"\x20" + address.to_bytes(3, "big"))
        finally:
            self.cs(1)

    @micropython.native
    def program_page(self, address, data):
        self.wait_not_busy()
        self.write_enable()
        self.cs(0)
        try:
            self.spi.write(b"\x02" + address.to_bytes(3, "big") + data)
        finally:
            self.cs(1)

    @micropython.native
    def program(self, address, data):
        offset = 0
        while offset < len(data):
            page_address = (address + offset) & ~(self.PAGE_SIZE - 1)
            page_offset = (address + offset) % self.PAGE_SIZE
            chunk_size = min(self.PAGE_SIZE - page_offset, len(data) - offset)
            chunk = data[offset : offset + chunk_size]
            self.program_page(page_address + page_offset, chunk)
            offset += chunk_size

    def program_sectors(self, start_address, verify=True):
        addr = start_address
        gc.collect()
        verify_buffer = bytearray(1)
        try:
            micropython.kbd_intr(-1)  # Disable Ctrl-C
            print(f"flash_prog={addr:X}")
            while True:
                line = sys.stdin.buffer.readline()
                if not line:
                    break
                chunk_length = int(line.strip())
                if chunk_length == 0:
                    break

                # Erase the sector while receiving the data
                end_address = addr + chunk_length
                for erase_addr in range(addr, end_address, self.SECTOR_SIZE):
                   self.erase_sector(erase_addr)

                chunk_data = sys.stdin.buffer.read(chunk_length)
                self.program(addr, chunk_data)

                if verify:
                    if chunk_length != len(verify_buffer):
                        verify_buffer = bytearray(chunk_length)
                    self.read_data_into(addr, verify_buffer)
                    if verify_buffer != chunk_data:
                        raise RuntimeError("Verification failed")

                addr += len(chunk_data)
                print(f"flash_prog={addr:X}")
        finally:
            micropython.kbd_intr(3)
        print(f"flash_prog=ok")

    @micropython.native
    def read_data_into(self, address, rdata):
        self.wait_not_busy()
        self.cs(0)
        try:
            self.spi.write(b"\x03" + address.to_bytes(3, "big"))
            return self.spi.readinto(rdata)
        finally:
            self.cs(1)

@rp2.asm_pio(autopush=True, push_thresh=8, in_shiftdir=rp2.PIO.SHIFT_LEFT,
             autopull=True, pull_thresh=8, out_shiftdir=rp2.PIO.SHIFT_RIGHT,
             out_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.IN_HIGH, rp2.PIO.OUT_HIGH,
                       rp2.PIO.IN_HIGH, rp2.PIO.IN_HIGH, rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH),
             sideset_init=(rp2.PIO.OUT_HIGH))
def qspi_read():
    out(x, 8).side(1)
    out(y, 8).side(1)
    out(pindirs, 8).side(1)
    
    label("cmd_loop")
    out(pins, 8).side(0)
    jmp(x_dec, "cmd_loop").side(1)
    
    out(pindirs, 8).side(0)
    label("data_loop")
    in_(pins, 8).side(1)
    jmp(y_dec, "data_loop").side(0)
    
    out(pins, 8).side(1)
    out(pindirs, 8).side(1)

@rp2.asm_pio(autopush=True, push_thresh=32, in_shiftdir=rp2.PIO.SHIFT_RIGHT)
def pio_capture():
    in_(pins, 8)
    
def spi_cmd(spi, data, sel, dummy_len=0, read_len=0):
    dummy_buf = bytearray(dummy_len)
    read_buf = bytearray(read_len)
    
    sel.off()
    spi.write(bytearray(data))
    if dummy_len > 0:
        spi.readinto(dummy_buf)
    if read_len > 0:
        spi.readinto(read_buf)
    sel.on()
    
    return read_buf

def setup_pmod():
    flash_sel = Pin(GPIO_UIO[0], Pin.OUT, value=1)
    ram_a_sel = Pin(GPIO_UIO[6], Pin.OUT, value=1)
    ram_b_sel = Pin(GPIO_UIO[7], Pin.OUT, value=1)
    
    spi = PIOSPI(2, Pin(GPIO_UIO[1]), Pin(GPIO_UIO[2]), Pin(GPIO_UIO[3]), freq=10000000)

    # Enter QPI mode on the RAM chips
    for sel in (ram_a_sel, ram_b_sel):
        spi_cmd(spi, [0x35], sel)

    # Leave CM mode if in it
    spi_cmd(spi, [0xFF], flash_sel)
    spi._sm.active(0)
    del spi

    sm = rp2.StateMachine(0, qspi_read, 16_000_000, in_base=Pin(GPIO_UIO[0]), out_base=Pin(GPIO_UIO[0]), sideset_base=Pin(GPIO_UIO[3]))
    sm.active(1)
    
    # Read 1 byte from address 0 to get into continuous read mode
    num_bytes = 4
    buf = bytearray(num_bytes*2 + 4)
    
    sm.put(8+6+2-1)     # Command + Address + Dummy - 1
    sm.put(num_bytes*2 + 4 - 1) # Data + Dummy - 1
    sm.put(0b11111111)  # Directions
    
    # RAM_B_SEL, RAM_A_SEL, SD3, SD2, SCK, SD1, SD0, CS
    sm.put(0b11000010)  # Command
    sm.put(0b11000010)
    sm.put(0b11000010)
    sm.put(0b11000000)
    sm.put(0b11000010)
    sm.put(0b11000000)
    sm.put(0b11000010)
    sm.put(0b11000010)
    
    sm.put(0b11000000)  # Address
    sm.put(0b11000000)
    sm.put(0b11000000)
    sm.put(0b11000000)
    sm.put(0b11000000)
    sm.put(0b11000000)
    sm.put(0b11100100) 
    sm.put(0b11100100)
    
    sm.put(0b11001001)  # Directions
    
    for i in range(num_bytes*2 + 4):
        buf[i] = sm.get()
        if i >= 4:
            d = buf[i]
            nibble = ((d >> 1) & 1) | ((d >> 1) & 2) | ((d >> 2) & 0x4) | ((d >> 2) & 0x8)
            #print("%01x" % (nibble,), end="")
    #print()
        
    sm.put(0b11111111)
    sm.put(0b11001001)  # Directions
    sm.active(0)
    del sm
    
    flash_sel = Pin(GPIO_UIO[0], Pin.OUT, value=1)
    ram_a_sel = Pin(GPIO_UIO[6], Pin.OUT, value=1)
    ram_b_sel = Pin(GPIO_UIO[7], Pin.OUT, value=1)

def run(query=False, stop=False):
    machine.freq(128_000_000)

    Pin(GPIO_UIO[0], Pin.IN, pull=Pin.PULL_UP)
    Pin(GPIO_UIO[1], Pin.IN, pull=None)
    Pin(GPIO_UIO[2], Pin.IN, pull=None)
    Pin(GPIO_UIO[3], Pin.IN, pull=None)
    Pin(GPIO_UIO[4], Pin.IN, pull=None)
    Pin(GPIO_UIO[5], Pin.IN, pull=None)
    Pin(GPIO_UIO[6], Pin.IN, pull=Pin.PULL_UP)
    Pin(GPIO_UIO[7], Pin.IN, pull=Pin.PULL_UP)

    print()
    select_design(227)

    if query:
        input("Reset? ")

    # Pull up UART RX
    Pin(GPIO_UI_IN[7], Pin.IN, pull=Pin.PULL_UP)
    
    # All other inputs pulled low
    for i in range(7):
        Pin(GPIO_UI_IN[i], Pin.IN, pull=Pin.PULL_DOWN)

    clk = Pin(GPIO_PROJECT_CLK, Pin.OUT, value=0)
    rst_n = Pin(GPIO_PROJECT_RST_N, Pin.OUT, value=1)
    for i in range(2):
        clk.on()
        clk.off()
    rst_n.off()
    
    clk.on()
    time.sleep(0.001)
    clk.off()
    time.sleep(0.001)

    setup_pmod()

    flash_sel = Pin(GPIO_UIO[0], Pin.OUT)
    qspi_sd0  = Pin(GPIO_UIO[1], Pin.OUT)
    qspi_sd1  = Pin(GPIO_UIO[2], Pin.OUT)
    qspi_sck  = Pin(GPIO_UIO[3], Pin.OUT)
    qspi_sd2  = Pin(GPIO_UIO[4], Pin.OUT)
    qspi_sd3  = Pin(GPIO_UIO[5], Pin.OUT)
    ram_a_sel = Pin(GPIO_UIO[6], Pin.OUT)
    ram_b_sel = Pin(GPIO_UIO[7], Pin.OUT)

    qspi_sck.off()
    flash_sel.off()
    ram_a_sel.off()
    ram_b_sel.off()
    qspi_sd0.off()
    qspi_sd1.on()
    qspi_sd2.off()
    qspi_sd3.off()

    for i in range(10):
        clk.off()
        time.sleep(0.001)
        clk.on()
        time.sleep(0.001)

    Pin(GPIO_UIO[0], Pin.IN, pull=Pin.PULL_UP)
    Pin(GPIO_UIO[1], Pin.IN, pull=None)
    Pin(GPIO_UIO[2], Pin.IN, pull=None)
    Pin(GPIO_UIO[3], Pin.IN, pull=None)
    Pin(GPIO_UIO[4], Pin.IN, pull=None)
    Pin(GPIO_UIO[5], Pin.IN, pull=None)
    Pin(GPIO_UIO[6], Pin.IN, pull=Pin.PULL_UP)
    Pin(GPIO_UIO[7], Pin.IN, pull=Pin.PULL_UP)
    
    rst_n.on()
    time.sleep(0.001)
    clk.off()

    sm = rp2.StateMachine(1, pio_capture, 128_000_000, in_base=Pin(GPIO_UIO[0]))

    capture_len=1024
    buf = bytearray(capture_len)

    rx_dma = rp2.DMA()
    c = rx_dma.pack_ctrl(inc_read=False, treq_sel=5) # Read using the SM0 RX DREQ
    sm.restart()
    sm.exec("wait(%d, gpio, %d)" % (1, GPIO_UIO[3]))
    rx_dma.config(
        read=0x5020_0024,        # Read from the SM1 RX FIFO
        write=buf,
        ctrl=c,
        count=capture_len//4,
        trigger=True
    )
    sm.active(1)

    if query:
        input("Start? ")

    uart = UART(1, baudrate=115200, tx=Pin(GPIO_UI_IN[7]), rx=Pin(GPIO_UO_OUT[0]), cts=Pin(GPIO_UO_OUT[1]))
    time.sleep(0.001)
    clk = PWM(Pin(GPIO_PROJECT_CLK), freq=64_000_000, duty_u16=32768)

    # Wait for DMA to complete
    while rx_dma.active():
        time.sleep_ms(1)
        
    sm.active(0)
    del sm

    if True:
        poll = uselect.poll()
        poll.register(sys.stdin, uselect.POLLIN)

        while True:
            if poll.poll(0):
                c = sys.stdin.buffer.read(1)

                # Repeat the character to workaround TinyQV bug
                uart.write(c)
                uart.write(c)

            uart_data = uart.read()
            if uart_data:
                sys.stdout.write(uart_data)

    if False:
        for j in range(8):
            print("%02d: " % (j+21,), end="")
            for d in buf:
                print("-" if (d & (1 << j)) != 0 else "_", end = "")
            print()

        print("SD: ", end="")
        for d in buf:
            nibble = ((d >> 1) & 1) | ((d >> 1) & 2) | ((d >> 2) & 0x4) | ((d >> 2) & 0x8)
            print("%01x" % (nibble,), end="")
        print()

def program_flash(start_address):
    select_design(0)
    flash = SPIFlash()
    flash.program_sectors(start_address)

select_design(0)
flash = SPIFlash()
print(f"tt.flash_id={binascii.hexlify(flash.identify()).decode()}")
del flash

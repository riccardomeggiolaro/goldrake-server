import cups
from weasyprint import HTML
import tempfile
import os
from typing import Dict, List, Union

"""
Linux debian dependencies:
    apt-get install libcups2-dev python3-dev cups python3-pycups build-essential libusb-1.0-0-dev
    sudo apt install hplip hplip-gui
    cd ~/Downloads
    chmod +x hplip-<version>.run
    ./hplip-<version>.run
    hp-setup
    sudo usermod -aG lp $(whoami)
"""

class HTMLPrinter:
    def __init__(self, printer_name):
        self.conn = cups.Connection()
        self.printer_name = printer_name
        
        # Verifica se la stampante esiste
        printers = self.conn.getPrinters()

    def get_printer_state_description(self, state: int) -> str:
        """
        Converte il codice dello stato della stampante in una descrizione leggibile.
        """
        states = {
            3: "Pronta",
            4: "In elaborazione",
            5: "Fermata",
        }
        return states.get(state, f"Stato sconosciuto ({state})")

    def interpret_state_reasons(self, reasons: List[str]) -> List[str]:
        """
        Interpreta le ragioni dello stato della stampante in modo leggibile.
        """
        reason_descriptions = {
            'marker-supply-low-warning': 'Livello inchiostro basso',
            'marker-supply-empty-warning': 'Cartuccia vuota',
            'toner-low': 'Toner basso',
            'toner-empty': 'Toner esaurito',
            'cover-open': 'Coperchio aperto',
            'door-open': 'Sportello aperto',
            'paper-empty': 'Carta esaurita',
            'paper-jam': 'Inceppamento carta',
            'media-empty': 'Vassio carta vuoto',
            'offline-report': 'Stampante offline'
        }
        
        return [reason_descriptions.get(reason, reason) for reason in reasons]

    def get_detailed_status(self) -> Dict[str, Union[str, List[str]]]:
        """
        Ottiene uno stato dettagliato e leggibile della stampante.
        """
        status = self.get_printer_status()
        
        detailed_status = {
            'nome': status.get('printer-info', 'Sconosciuto'),
            'stato': self.get_printer_state_description(status.get('printer-state')),
            'messaggi': self.interpret_state_reasons(status.get('printer-state-reasons', [])),
            'modello': status.get('printer-make-and-model', 'Sconosciuto'),
            'condivisa': 'Sì' if status.get('printer-is-shared') else 'No',
            'uri_dispositivo': status.get('device-uri', 'Sconosciuto')
        }
        
        return detailed_status

    def print_html(self, html_content):
        """
        Stampa una stringa HTML utilizzando CUPS.
        Se la stampante è offline, il lavoro rimarrà in coda fino a quando non sarà disponibile.

        Args:
            html_content (str): Il contenuto HTML da stampare.
            printer_name (str): Nome della stampante. Se None, utilizza la stampante predefinita.
        """

        job_id = None

        # Controlla lo stato della stampante
        printers = self.conn.getPrinters()
        printer_status = printers.get(self.printer_name, {}).get('printer-state', None)

        if printer_status == cups.IPP_PRINTER_STOPPED:
            print(f"Avviso: La stampante '{self.printer_name}' è attualmente ferma o offline. La stampa rimarrà in coda.")

        # Crea un file temporaneo per il contenuto HTML
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
            temp_file.write(html_content.encode('utf-8'))
            temp_file_path = temp_file.name

        # Invia il file HTML alla stampante
        try:
            job_id = self.conn.printFile(self.printer_name, temp_file_path, "HTML Print Job", {})
            print(f"Stampa inviata alla stampante '{self.printer_name}' con successo. La stampa rimarrà in coda se la stampante è offline.")
        except Exception as e:
            print(f"Errore durante la stampa: {e}")
        finally:
            # Rimuovi il file temporaneo
            os.unlink(temp_file_path)

        return job_id

    def get_printer_status(self) -> Dict:
        """
        Ottiene lo stato della stampante.
        """
        printers = self.conn.getPrinters()
        return printers.get(self.printer_name, {})

    def get_job_status(self, job_id: int) -> Dict:
        """
        Ottiene lo stato di un lavoro di stampa specifico.
        
        Args:
            job_id (int): ID del lavoro di stampa
            
        Returns:
            dict: Informazioni sul lavoro di stampa o None se non trovato
        """
        jobs = self.conn.getJobs()
        return jobs.get(job_id)

    def cancel_job(self, job_id: int) -> bool:
        """
        Annulla un lavoro di stampa specifico.
        
        Args:
            job_id (int): ID del lavoro di stampa da annullare
            
        Returns:
            bool: True se l'annullamento è riuscito, False altrimenti
        """
        try:
            self.conn.cancelJob(job_id)
            return True
        except cups.IPPError as e:
            print(f"Errore nell'annullamento del lavoro {job_id}: {str(e)}")
            return False

    def get_active_jobs(self) -> Dict:
        """
        Ottiene tutti i lavori di stampa attivi.
        
        Returns:
            dict: Dizionario dei lavori di stampa attivi
        """
        return self.conn.getJobs(which_jobs='not-completed')

    def get_job_state_description(self, state: int) -> str:
        """
        Converte il codice dello stato del lavoro in una descrizione leggibile.
        """
        states = {
            3: "Pending",
            4: "In attesa di essere elaborato",
            5: "In elaborazione",
            6: "Fermato",
            7: "Annullato",
            8: "Abortito",
            9: "Completato"
        }
        return states.get(state, f"Stato sconosciuto ({state})")

    def get_detailed_job_info(self, job_id: int) -> Dict:
        """
        Ottiene informazioni dettagliate su un lavoro di stampa specifico.
        
        Args:
            job_id (int): ID del lavoro di stampa
            
        Returns:
            dict: Informazioni dettagliate sul lavoro o None se non trovato
        """
        try:
            job_attrs = self.conn.getJobAttributes(job_id)
            return {
                'id': job_id,
                'nome': job_attrs.get('job-name', 'Sconosciuto'),
                'stato': self.get_job_state_description(job_attrs.get('job-state', 0)),
                'utente': job_attrs.get('job-originating-user-name', 'Sconosciuto'),
                'dimensione': job_attrs.get('job-k-octets', 0),
                'pagine': job_attrs.get('job-media-sheets', 'Sconosciuto'),
                'priorità': job_attrs.get('job-priority', 50),
                'ora_creazione': job_attrs.get('time-at-creation', 0)
            }
        except cups.IPPError:
            return None

if __name__ == "__main__":
    # Esempio di contenuto HTML
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Test di stampa</title>
        </head>
        <body>
            <h1>Test di stampa HTML</h1>
            <p>Questo è un test di stampa usando Python.</p>
        </body>
    </html>
    """
    
    try:
        printer = HTMLPrinter()
        
        # Stampa il contenuto
        job_id = printer.print_html(html_content)
        print(f"Lavoro di stampa inviato con ID: {job_id}")
        
        # Mostra lo stato dettagliato della stampante
        status = printer.get_detailed_status()
        print("\nStato dettagliato della stampante:")
        for key, value in status.items():
            print(f"{key.capitalize()}: {value}")
        
        # Mostra i dettagli del lavoro di stampa
        job_info = printer.get_detailed_job_info(job_id)
        if job_info:
            print("\nDettagli del lavoro di stampa:")
            for key, value in job_info.items():
                print(f"{key.capitalize()}: {value}")
        
        # Esempio di come annullare il lavoro (commentato per sicurezza)
        # if input("\nVuoi annullare il lavoro? (s/n): ").lower() == 's':
        #     if printer.cancel_job(job_id):
        #         print(f"Lavoro {job_id} annullato con successo")
        #     else:
        #         print(f"Impossibile annullare il lavoro {job_id}")
        
    except Exception as e:
        print(f"Errore durante la stampa: {str(e)}")